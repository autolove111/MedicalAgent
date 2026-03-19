package com.medlab.service;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import java.util.HashMap;
import java.util.Map;

@Service
public class MedicalFacadeService {

    @Autowired
    private StorageService storageService;

    @Autowired(required = false)
    private UserMedicalService userMedicalService;

    public Map<String, String> handleUploadAndAppend(MultipartFile file, String authHeader) {
        Map<String, String> resp = new HashMap<>();
        try {
            String path = storageService.store(file);
            resp.put("status", "success");
            resp.put("path", path);
            // 后续可在此处触发解析、入库等操作
            return resp;
        } catch (Exception e) {
            resp.put("status", "error");
            resp.put("message", e.getMessage());
            return resp;
        }
    }
}
