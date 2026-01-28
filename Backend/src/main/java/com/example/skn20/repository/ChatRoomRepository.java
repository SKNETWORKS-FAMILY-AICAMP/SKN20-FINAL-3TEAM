package com.example.skn20.repository;

import com.example.skn20.entity.ChatRoom;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;
import java.util.List;
import com.example.skn20.entity.User;


@Repository
public interface ChatRoomRepository extends JpaRepository<ChatRoom, Long> {
	List<ChatRoom> findAllByUser(User user);
	ChatRoom findChatRoomById(Long id);
	void deleteAllById(Long id);
}
