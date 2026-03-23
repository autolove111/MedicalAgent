package com.medlab.controller;

import com.medlab.service.VisionService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.FileSystemResource;
import org.springframework.core.io.Resource;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import java.io.File;
import java.io.IOException;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

@RestController
@RequestMapping("/api/v1/file")
public class FileController {

    @Value("${medlab.upload.dir}")
    private String uploadDir;

    @Value("${medlab.upload.max-file-size:104857600}")
    private long maxFileSize;

    @Value("${medlab.upload.allowed-types:jpg,jpeg,png,pdf,gif,webp}")
    private String allowedTypes;

    @Value("${medlab.server.url:http://localhost:8080}")
    private String serverUrl;

    @Value("${medlab.server.ocr-access-url:http://host.docker.internal:8080}")
    private String ocrAccessUrl;

    private final VisionService visionService;

    @Autowired
    public FileController(VisionService visionService) {
        this.visionService = visionService;
    }

    @PostMapping("/upload-report")
    public ResponseEntity<?> uploadReport(@RequestParam("file") MultipartFile file) {
        Map<String, Object> response = new HashMap<>();

        if (file.isEmpty()) {
            response.put("status", "error");
            response.put("message", "文件为空，请选择有效文件");
            return ResponseEntity.badRequest().body(response);
        }

        if (file.getSize() > maxFileSize) {
            response.put("status", "error");
            response.put("message", "文件过大，超出限制");
            return ResponseEntity.badRequest().body(response);
        }

        String originalFilename = file.getOriginalFilename();
        if (!isAllowedFileType(originalFilename)) {
            response.put("status", "error");
            response.put("message", "不支持的文件类型");
            return ResponseEntity.badRequest().body(response);
        }

        try {
            File uploadDirectory = new File(uploadDir);
            if (!uploadDirectory.exists()) {
                uploadDirectory.mkdirs();
            }

            String fileName = UUID.randomUUID() + "-" + originalFilename;
            File destinationFile = new File(uploadDir, fileName);
            file.transferTo(destinationFile);

            String browserFileUrl = serverUrl + "/api/v1/file/view/" + fileName;
            String ocrAccessibleUrl = ocrAccessUrl + "/api/v1/file/view/" + fileName;

            visionService.prefetchOcr(ocrAccessibleUrl);

            response.put("status", "success");
            response.put("message", "文件上传成功，OCR 预取已启动");
            response.put("fileName", fileName);
            response.put("filePath", ocrAccessibleUrl);
            response.put("fileUrl", browserFileUrl);
            response.put("previewUrl", browserFileUrl);
            response.put("originalName", originalFilename);
            return ResponseEntity.ok(response);
        } catch (IOException e) {
            response.put("status", "error");
            response.put("message", "文件保存失败: " + e.getMessage());
            return ResponseEntity.status(500).body(response);
        } catch (Exception e) {
            response.put("status", "error");
            response.put("message", "上传过程中发生错误: " + e.getMessage());
            return ResponseEntity.status(500).body(response);
        }
    }

    private boolean isAllowedFileType(String filename) {
        if (filename == null || filename.isEmpty() || !filename.contains(".")) {
            return false;
        }

        String extension = filename.substring(filename.lastIndexOf(".") + 1).toLowerCase();
        String[] allowed = allowedTypes.split(",");
        for (String type : allowed) {
            if (extension.equals(type.trim())) {
                return true;
            }
        }
        return false;
    }

    @GetMapping("/health")
    public ResponseEntity<?> health() {
        Map<String, String> response = new HashMap<>();
        response.put("status", "healthy");
        response.put("uploadDir", uploadDir);
        return ResponseEntity.ok(response);
    }

    @GetMapping("/view/{fileName}")
    public ResponseEntity<Resource> viewFile(@PathVariable String fileName) {
        try {
            Path filePath = Paths.get(uploadDir).resolve(fileName);
            if (!filePath.normalize().startsWith(Paths.get(uploadDir).normalize())) {
                return ResponseEntity.notFound().build();
            }

            File file = filePath.toFile();
            if (!file.exists()) {
                return ResponseEntity.notFound().build();
            }

            Resource resource = new FileSystemResource(file);
            String contentType = "application/octet-stream";
            String lower = fileName.toLowerCase();
            if (lower.endsWith(".jpg") || lower.endsWith(".jpeg")) {
                contentType = "image/jpeg";
            } else if (lower.endsWith(".png")) {
                contentType = "image/png";
            } else if (lower.endsWith(".gif")) {
                contentType = "image/gif";
            } else if (lower.endsWith(".pdf")) {
                contentType = "application/pdf";
            } else if (lower.endsWith(".webp")) {
                contentType = "image/webp";
            }

            return ResponseEntity.ok()
                    .header(HttpHeaders.CONTENT_DISPOSITION, "inline; filename=\"" + fileName + "\"")
                    .contentType(MediaType.parseMediaType(contentType))
                    .body(resource);
        } catch (Exception e) {
            return ResponseEntity.status(500).build();
        }
    }
}
