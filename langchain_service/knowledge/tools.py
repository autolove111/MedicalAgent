from contextvars import ContextVar
from typing import Optional, Dict, Any
import logging
import uuid

import requests
from langchain_core.tools import Tool
from contextvars import ContextVar
from typing import Optional, Dict, Any
import logging
import uuid

import requests
from langchain_core.tools import Tool
from sqlalchemy import create_engine

from core.config import settings

logger = logging.getLogger(__name__)

_current_user_id: ContextVar[Optional[str]] = ContextVar("current_user_id", default=None)
_failed_history_user_ids = set()
_failed_age_profile_user_ids = set()


def _normalize_uuid(user_id: Optional[str]) -> Optional[str]:
    """规范化 UUID；非法值返回 None。"""
    if not user_id or not isinstance(user_id, str):
        return None
    raw = user_id.strip()
    if raw in {"当前用户", "无用户ID", "anonymous", "test-user-123"}:
        return None
    try:
        return str(uuid.UUID(raw))
    except Exception:
        return None


def set_current_user_id(user_id: Optional[str]):
    _current_user_id.set(_normalize_uuid(user_id))


def get_current_user_id() -> Optional[str]:
    return _current_user_id.get()


try:
    engine = create_engine(settings.SQLALCHEMY_DATABASE_URL)
except Exception as e:
    logger.warning(f"数据库连接失败: {e}")
    engine = None


def query_medical_knowledge(
    keyword: str,
    scope: str = "main",
    department: Optional[str] = None,
    indicator: Optional[str] = None,
    direction: Optional[str] = None,
) -> str:
    """统一知识检索入口: 强制使用 embeddings/向量检索（优先 rag，随后本地 vectorstore）。"""
    composed = (keyword or "").strip()
    if indicator:
        composed = f"{composed} {indicator}".strip()
    if direction:
        dir_text = {"high": "升高", "low": "降低", "normal": "正常"}.get(direction, str(direction))
        composed = f"{composed} {dir_text}".strip()

    logger.info(
        "[TOOLS][Knowledge] start | scope=%s dept=%s keyword=%s",
        scope,
        department,
        (composed or "")[:160],
    )

    # 优先使用 legacy rag 模块
    try:
        from knowledge.rag import retrieve_medical_knowledge as retrieve_via_rag

        result, sources = retrieve_via_rag(composed, scope=scope, department=department)
        if result and str(result).strip():
            logger.info(
                "[TOOLS][Knowledge] done(rag) | scope=%s dept=%s chars=%d sources=%d",
                scope,
                department,
                len(result),
                len(sources or []),
            )
            return result
    except Exception:
        logger.debug("rag module not available or failed")

    # 回退到本地 KnowledgeBase 的向量索引（必须存在）
    try:
        from knowledge.medical_knowledge import create_knowledge_base

        kb = create_knowledge_base()
        if not kb:
            return (
                "【知识库未初始化】无法执行 embeddings 检索。"
                " 请在 `langchain_service/.env` 中设置 `DASHSCOPE_API_KEY`，并运行向量构建脚本。"
            )

        if not getattr(kb, 'vectorstore', None):
            return (
                "【向量索引缺失】本地 KnowledgeBase 未构建向量索引。"
                " 请运行: python -m langchain_service.knowledge.build_vectorstore"
            )

        retriever = kb.vectorstore.as_retriever(search_kwargs={"k": getattr(settings, 'RAG_TOP_K', 3)})
        docs = retriever.get_relevant_documents(composed)
        if not docs:
            logger.info("[TOOLS][Knowledge] empty(vector) | scope=%s dept=%s", scope, department)
            return f"【知识库检索结果】未找到关键字 '{composed}' 的相关医学文献"

        snippets = []
        for d in docs:
            src = getattr(d, 'metadata', {}).get('source', 'local')
            snippets.append(f"【{src}】 {d.page_content[:800].strip()}")

        out_text = "\n\n".join(snippets)
        logger.info("[TOOLS][Knowledge] done(vector) | scope=%s dept=%s snippets=%d", scope, department, len(snippets))
        return "【知识库检索结果】\n" + out_text
    except Exception as e:
        logger.exception(f"Embeddings 检索异常: {e}")
        return ("【检索异常】Embeddings 检索失败：" + str(e) + "。")


def query_user_medical_history(user_id: Optional[str]) -> str:
    explicit_user_id = _normalize_uuid(user_id)
    context_user_id = _normalize_uuid(get_current_user_id())
    effective_user_id = explicit_user_id or context_user_id
    if not effective_user_id:
        return "【用户信息】当前为匿名访问模式，无法查询用户既往史。建议登录后重试以获取个性化建议。"

    if effective_user_id in _failed_history_user_ids:
        return "【既往史】暂无病历记录\n【过敏信息】无已知过敏史"

    backend = getattr(settings, "BACKEND_URL", "http://localhost:8080")
    try:
        logger.info("[TOOLS][History] start | user_id=%s", effective_user_id)
        url = f"{backend}/api/v1/internal/user/medical-history"
        resp = requests.get(url, params={"userId": effective_user_id}, timeout=5)
        if resp.status_code != 200:
            logger.warning(f"后端返回非 200: {resp.status_code} {resp.text}")
            if resp.status_code == 400:
                _failed_history_user_ids.add(effective_user_id)
            return "【既往史】暂无病历记录\n【过敏信息】无已知过敏史"
        data = resp.json()
        if data.get("status") == "success":
            med_history = data.get("medicalHistory", "无")
            drug_allergy = data.get("drugAllergy", "无")
            logger.info(
                "[TOOLS][History] done | user_id=%s med_len=%d allergy_len=%d",
                effective_user_id,
                len(str(med_history or "")),
                len(str(drug_allergy or "")),
            )
            return f"【既往史】{med_history}\n【过敏信息】{drug_allergy}"
        return f"【后端错误】{data.get('message', '未知错误')}"
    except Exception as e:
        logger.error(f"查询用户病历异常: {e}")
        return f"【系统异常】无法查询病历: {str(e)}"


def query_user_age_profile(user_id: Optional[str]) -> Dict[str, Any]:
    explicit_user_id = _normalize_uuid(user_id)
    context_user_id = _normalize_uuid(get_current_user_id())
    effective_user_id = explicit_user_id or context_user_id
    if not effective_user_id:
        return {}

    if effective_user_id in _failed_age_profile_user_ids:
        return {"is_pediatric": False}

    backend = getattr(settings, "BACKEND_URL", "http://localhost:8080")
    try:
        url = f"{backend}/api/v1/internal/user/profile"
        resp = requests.get(url, params={"userId": effective_user_id}, timeout=5)
        if resp.status_code != 200:
            logger.warning(f"年龄画像接口返回非 200: {resp.status_code} {resp.text}")
            if resp.status_code == 400:
                _failed_age_profile_user_ids.add(effective_user_id)
            return {}

        data = resp.json() or {}
        if data.get("status") != "success":
            return {}

        out: Dict[str, Any] = {}
        age_years = data.get("ageYears")
        if age_years is not None:
            try:
                out["age_years"] = float(age_years)
            except Exception:
                pass
        out["is_pediatric"] = bool(data.get("isPediatric", False))
        return out
    except Exception as e:
        logger.error(f"查询用户年龄画像异常: {e}")
        return {}


def classify_medical_report(content: str) -> str:
    keywords_map = {
        "血液": "血液检查",
        "CBC": "血液检查",
        "肝功": "肝功能检查",
        "Liver": "肝功能检查",
        "肾功": "肾功能检查",
        "Kidney": "肾功能检查",
        "血糖": "代谢检查",
        "葡萄糖": "代谢检查",
        "心电": "心脏检查",
        "ECG": "心脏检查",
        "尿": "尿液检查",
        "Urine": "尿液检查",
    }

    for keyword, classification in keywords_map.items():
        if keyword in content:
            return classification

    return "综合医学报告"


def analyze_medical_image(image_input: str) -> str:
    from vision.vision_analyzer import analyze_medical_image as _analyze_medical_image
    return _analyze_medical_image(image_input)


def recheck_medical_image(payload: str) -> str:
    from vision.vision_analyzer import recheck_medical_image as _recheck_medical_image
    return _recheck_medical_image(payload)


tools = [
    Tool(
        name="QueryMedicalKnowledge",
        func=query_medical_knowledge,
        description="从医学知识库查询相关医学信息。输入：医学关键词。",
    ),
    Tool(
        name="QueryUserHistory",
        func=query_user_medical_history,
        description="查询当前用户的既往史、过敏信息。输入必须是 UUID 格式的 user_id。",
    ),
    Tool(
        name="QueryUserAgeProfile",
        func=query_user_age_profile,
        description="查询当前用户年龄画像。输入必须是 UUID 格式的 user_id，返回 age_years/is_pediatric。",
    ),
    Tool(
        name="ClassifyReport",
        func=classify_medical_report,
        description="自动分类医疗报告类型。输入：报告内容。",
    ),
    Tool(
        name="AnalyzeMedicalImage",
        func=analyze_medical_image,
        description=(
            "分析医学化验单图片。输入图片本地路径或 URL。"
            "该工具会先访问 OCR 缓存服务；如果 Java 已提前预取，通常会直接命中缓存。"
        ),
    ),
    Tool(
        name="RecheckMedicalImage",
        func=recheck_medical_image,
        description=(
            "对 OCR 结果做高精度二次核对。输入格式必须是 图片路径||重点复核项目 。"
        ),
    ),
]















