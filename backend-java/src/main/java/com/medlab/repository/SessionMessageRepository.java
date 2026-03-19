package com.medlab.repository;

import com.medlab.entity.SessionMessage;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.UUID;

@Repository
public interface SessionMessageRepository extends JpaRepository<SessionMessage, UUID> {
    List<SessionMessage> findByUserIdOrderByCreatedAtAsc(UUID userId);
    void deleteByUserId(UUID userId);
}
