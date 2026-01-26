package com.example.skn20.entity;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDate;
import java.util.List;

import org.hibernate.annotations.CreationTimestamp;

import com.fasterxml.jackson.annotation.JsonManagedReference;

@Entity
@Table(name = "Chatroom")
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class ChatRoom {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne
    @JoinColumn(name = "user_id", nullable = false)
    private User user; // 사용자 정보
    
    private String name; // 채팅방 요약된 제목
    
    @Column(name = "created_at", nullable = false)
    @CreationTimestamp
    private LocalDate createdAt; // 생성 일자

    @OneToMany
    @JoinColumn(name = "chathistory_id", nullable = true)
    @JsonManagedReference
    private List<ChatHistory> chatHistory; // 채팅 내역
}
