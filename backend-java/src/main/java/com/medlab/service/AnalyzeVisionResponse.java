package com.medlab.service;

import java.util.List;

public class AnalyzeVisionResponse {
    private String status;
    private String file_path;
    private String model;
    private List<VisionItem> analysis;
    private String message;
    private Boolean cached;
    private String cache_key;

    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }

    public String getFile_path() { return file_path; }
    public void setFile_path(String file_path) { this.file_path = file_path; }

    public String getModel() { return model; }
    public void setModel(String model) { this.model = model; }

    public List<VisionItem> getAnalysis() { return analysis; }
    public void setAnalysis(List<VisionItem> analysis) { this.analysis = analysis; }

    public String getMessage() { return message; }
    public void setMessage(String message) { this.message = message; }

    public Boolean getCached() { return cached; }
    public void setCached(Boolean cached) { this.cached = cached; }

    public String getCache_key() { return cache_key; }
    public void setCache_key(String cache_key) { this.cache_key = cache_key; }

    public static AnalyzeVisionResponse errorResponse(String message) {
        AnalyzeVisionResponse response = new AnalyzeVisionResponse();
        response.setStatus("error");
        response.setMessage(message);
        return response;
    }
}
