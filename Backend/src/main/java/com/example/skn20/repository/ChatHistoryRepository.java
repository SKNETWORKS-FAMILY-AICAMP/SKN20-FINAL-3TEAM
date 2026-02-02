package com.example.skn20.repository;

import java.util.List;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import com.example.skn20.entity.ChatHistory;
import com.example.skn20.entity.ChatRoom;


@Repository
public interface ChatHistoryRepository extends JpaRepository<ChatHistory, Long>{
	void deleteAllByChatRoom(ChatRoom chatRoom);
	List<ChatHistory> findAllByChatRoomOrderByIdAsc(ChatRoom chatRoom);
}
