package com.medlab.controller;

import com.medlab.entity.User;
import com.medlab.repository.UserRepository;
import com.medlab.util.JwtTokenProvider;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.HashMap;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;

@RestController
@RequestMapping("/api/v1")
@CrossOrigin(origins = "*")
public class UserController {

    @Autowired
    private JwtTokenProvider jwtTokenProvider;

    @Autowired
    private UserRepository userRepository;

    @GetMapping("/user/profile")
    public ResponseEntity<?> getProfile(@RequestHeader(value = "Authorization", required = false) String authHeader) {
        try {
            if (authHeader == null || !authHeader.startsWith("Bearer ")) {
                return ResponseEntity.status(401).body(Map.of("error", "Unauthorized"));
            }
            String token = authHeader.substring(7);
            UUID userId = jwtTokenProvider.getUserIdFromToken(token);
            Optional<User> opt = userRepository.findById(userId);
            if (opt.isEmpty()) {
                return ResponseEntity.status(404).body(Map.of("error", "User not found"));
            }
            User u = opt.get();
            Map<String, Object> data = new HashMap<>();
            data.put("id", u.getId());
            data.put("realName", u.getRealName());
            data.put("idNumber", u.getIdNumber());
            data.put("age", u.getAge());
            data.put("drugAllergy", u.getDrugAllergy());
            data.put("lifetimeMedicalHistory", u.getLifetimeMedicalHistory());
            return ResponseEntity.ok(Map.of("status", "success", "data", data));
        } catch (Exception e) {
            return ResponseEntity.status(500).body(Map.of("error", e.getMessage()));
        }
    }

        @RequestMapping(value = "/user/profile", method = {RequestMethod.PUT, RequestMethod.POST})
        public ResponseEntity<?> updateProfile(
            @RequestHeader(value = "Authorization", required = false) String authHeader,
            @RequestBody Map<String, Object> body
    ) {
        try {
            if (authHeader == null || !authHeader.startsWith("Bearer ")) {
                return ResponseEntity.status(401).body(Map.of("error", "Unauthorized"));
            }
            String token = authHeader.substring(7);
            UUID userId = jwtTokenProvider.getUserIdFromToken(token);
            Optional<User> opt = userRepository.findById(userId);
            if (opt.isEmpty()) {
                return ResponseEntity.status(404).body(Map.of("error", "User not found"));
            }
            User u = opt.get();
            if (body.containsKey("realName")) {
                u.setRealName((String) body.get("realName"));
            }
            if (body.containsKey("age")) {
                Object ageObj = body.get("age");
                if (ageObj != null) {
                    Integer age = null;
                    if (ageObj instanceof Number) age = ((Number) ageObj).intValue();
                    else age = Integer.parseInt(ageObj.toString());
                    u.setAge(age);
                }
            }
            if (body.containsKey("drugAllergy")) {
                u.setDrugAllergy((String) body.get("drugAllergy"));
            }
            if (body.containsKey("lifetimeMedicalHistory")) {
                u.setLifetimeMedicalHistory((String) body.get("lifetimeMedicalHistory"));
            }
            userRepository.save(u);
            return ResponseEntity.ok(Map.of("status", "success", "message", "Profile updated"));
        } catch (Exception e) {
            return ResponseEntity.status(500).body(Map.of("error", e.getMessage()));
        }
    }

    /**
     * 前端兼容接口：更新药物过敏（回退方案）
     */
    @PostMapping("/user/drug-allergy/update")
    public ResponseEntity<?> updateDrugAllergy(
            @RequestHeader(value = "Authorization", required = false) String authHeader,
            @RequestParam(value = "drugAllergy", required = false) String drugAllergy
    ) {
        try {
            if (authHeader == null || !authHeader.startsWith("Bearer ")) {
                return ResponseEntity.status(401).body(Map.of("error", "Unauthorized"));
            }
            String token = authHeader.substring(7);
            UUID userId = jwtTokenProvider.getUserIdFromToken(token);
            Optional<User> opt = userRepository.findById(userId);
            if (opt.isEmpty()) {
                return ResponseEntity.status(404).body(Map.of("error", "User not found"));
            }
            User u = opt.get();
            u.setDrugAllergy(drugAllergy != null ? drugAllergy : "");
            userRepository.save(u);
            return ResponseEntity.ok(Map.of("status", "success", "message", "Drug allergy updated"));
        } catch (Exception e) {
            return ResponseEntity.status(500).body(Map.of("error", e.getMessage()));
        }
    }

    /**
     * 前端兼容接口：追加病史记录
     */
    @PostMapping("/user/medical-history/append")
    public ResponseEntity<?> appendMedicalHistory(
            @RequestHeader(value = "Authorization", required = false) String authHeader,
            @RequestParam(value = "disease", required = false) String disease,
            @RequestParam(value = "status", required = false) String status
    ) {
        try {
            if (authHeader == null || !authHeader.startsWith("Bearer ")) {
                return ResponseEntity.status(401).body(Map.of("error", "Unauthorized"));
            }
            String token = authHeader.substring(7);
            UUID userId = jwtTokenProvider.getUserIdFromToken(token);
            Optional<User> opt = userRepository.findById(userId);
            if (opt.isEmpty()) {
                return ResponseEntity.status(404).body(Map.of("error", "User not found"));
            }
            User u = opt.get();
            String existing = u.getLifetimeMedicalHistory() != null ? u.getLifetimeMedicalHistory() : "";
            String toAppend = (disease != null ? disease : "") + (status != null ? (" (" + status + ")") : "");
            if (!toAppend.isBlank()) {
                if (!existing.isBlank()) existing = existing + "\n" + toAppend;
                else existing = toAppend;
                u.setLifetimeMedicalHistory(existing);
                userRepository.save(u);
            }
            return ResponseEntity.ok(Map.of("status", "success", "message", "Medical history appended"));
        } catch (Exception e) {
            return ResponseEntity.status(500).body(Map.of("error", e.getMessage()));
        }
    }

    /**
     * 前端兼容接口：获取当前用户的病史
     */
    @GetMapping("/user/medical-history")
    public ResponseEntity<?> getMedicalHistory(
            @RequestHeader(value = "Authorization", required = false) String authHeader
    ) {
        try {
            if (authHeader == null || !authHeader.startsWith("Bearer ")) {
                return ResponseEntity.status(401).body(Map.of("error", "Unauthorized"));
            }
            String token = authHeader.substring(7);
            UUID userId = jwtTokenProvider.getUserIdFromToken(token);
            Optional<User> opt = userRepository.findById(userId);
            if (opt.isEmpty()) {
                return ResponseEntity.status(404).body(Map.of("error", "User not found"));
            }
            User u = opt.get();
            Map<String, Object> data = new HashMap<>();
            data.put("medicalHistory", u.getLifetimeMedicalHistory() != null ? u.getLifetimeMedicalHistory() : "");
            data.put("drugAllergy", u.getDrugAllergy() != null ? u.getDrugAllergy() : "");
            return ResponseEntity.ok(Map.of("status", "success", "data", data));
        } catch (Exception e) {
            return ResponseEntity.status(500).body(Map.of("error", e.getMessage()));
        }
    }
}
