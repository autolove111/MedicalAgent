package com.medlab.service;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import java.util.HashMap;
import java.util.Map;

@Service
public class MedicalFacadeService {

    private final StorageService storageService;
    private final VisionService visionService;

    @Value("${medlab.server.url:http://localhost:8080}")
    private String serverUrl;

    @Value("${medlab.server.ocr-access-url:http://host.docker.internal:8080}")
    private String ocrAccessUrl;

    public MedicalFacadeService(StorageService storageService, VisionService visionService) {
        this.storageService = storageService;
        this.visionService = visionService;
    }

    public Map<String, String> handleUploadAndAppend(MultipartFile file, String authHeader) {
        Map<String, String> resp = new HashMap<>();
        try {
            String path = storageService.store(file);
            String normalizedPath = path.replace("\\", "/");
            String fileName = normalizedPath.substring(normalizedPath.lastIndexOf("/") + 1);

            String browserFileUrl = serverUrl + "/api/v1/file/view/" + fileName;
            String ocrAccessibleUrl = ocrAccessUrl + "/api/v1/file/view/" + fileName;

            visionService.prefetchOcr(ocrAccessibleUrl);

            resp.put("status", "success");
            resp.put("filePath", ocrAccessibleUrl);
            resp.put("fileUrl", browserFileUrl);
            resp.put("previewUrl", browserFileUrl);
            resp.put("fileName", fileName);
            resp.put("storedPath", normalizedPath);
            return resp;
        } catch (Exception e) {
            resp.put("status", "error");
            resp.put("message", e.getMessage());
            return resp;
        }
    }
}