package com.medlab.service;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.util.concurrent.CompletableFuture;

@Service
public class VisionService {

    private static final Logger logger = LoggerFactory.getLogger(VisionService.class);

    private final OcrServiceClient ocrServiceClient;

    public VisionService(OcrServiceClient ocrServiceClient) {
        this.ocrServiceClient = ocrServiceClient;
    }

    /**
     * Upload succeeds first, then Java immediately warms OCR cache on port 8001.
     * Failures are logged only and never block the main request.
     */
    public void prefetchOcr(String imagePath) {
        CompletableFuture.runAsync(() -> {
            try {
                logger.info("Starting OCR speculative prefetch for {}", imagePath);
                ocrServiceClient.prefetchVisionCache(imagePath, null).block();
                logger.info("OCR speculative prefetch finished for {}", imagePath);
            } catch (Exception ex) {
                logger.warn("OCR speculative prefetch failed for {}: {}", imagePath, ex.getMessage());
            }
        });
    }
}
