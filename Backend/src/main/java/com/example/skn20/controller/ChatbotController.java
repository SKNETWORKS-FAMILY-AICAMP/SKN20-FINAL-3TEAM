package com.example.skn20.controller;

import java.util.List;
import java.util.Map;

import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.CrossOrigin;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.example.skn20.classes.UD;
import com.example.skn20.entity.ChatHistory;
import com.example.skn20.entity.ChatRoom;
import com.example.skn20.entity.User;
import com.example.skn20.repository.ChatHistoryRepository;
import com.example.skn20.repository.ChatRoomRepository;
import com.example.skn20.service.ChatbotService;
import com.example.skn20.service.UserService;

import lombok.RequiredArgsConstructor;

@RestController
@RequestMapping("/api/chatbot")
@RequiredArgsConstructor
@CrossOrigin(origins = { "http://localhost:3000", "http://localhost:8000" })
public class ChatbotController {

	private final UserService userservice;
	
	private final ChatbotService chatbotService;
	
	private final ChatRoomRepository chatRoomRep;
	
	private final ChatHistoryRepository chatHistoryRep;
	
//	웹 페이지 접속시 해당 유저의 채팅 history를 가져옵니다
	@PostMapping("/sessionuser")
	public ResponseEntity<List<ChatRoom>> SesstoinUser(@AuthenticationPrincipal UD user) {
		User userinfo = userservice.findByEmail(user.getEmail());
		List<ChatRoom> chatRooms = chatRoomRep.findAllByUser(userinfo);

		return ResponseEntity.ok(chatRooms);
	}

// 해당 방을 클릭시 history를 가져옵니다
	@PostMapping("/roomhistory")
	public ResponseEntity<List<ChatHistory>> RoomHistory(@AuthenticationPrincipal UD user, @RequestParam Long chatRoomId) {
		User userinfo = userservice.findByEmail(user.getEmail());
		ChatRoom chatRoom = chatRoomRep.findChatRoomById(chatRoomId);
		if (chatRoom.getUser().getId() != userinfo.getId()) {
			return ResponseEntity.status(403).body(null);
		}
		List<ChatHistory> chatHistories = chatHistoryRep.findAllByChatRoomOrderByIdAsc(chatRoom);
		return ResponseEntity.ok(chatHistories);
	}
	
//	해당 유저의 정보의 질문을 받고 LLM에 보낸뒤 값을 반환해줍니다.
	@PostMapping("/chat")
	@Transactional
	public ResponseEntity<String> question2answer(@AuthenticationPrincipal UD user, @RequestParam(required = false) Long chatRoomId, @RequestParam String question) {
		User userinfo = userservice.findByEmail(user.getEmail());
        Map<String, String> result = chatbotService.question2answer(userinfo, question);
        String answer =  result.get("answer");
        
        if (chatRoomId == null) {
        	ChatRoom chatRoom = new ChatRoom();
        	chatRoom.setName(result.get("summaryTitle"));
        	chatRoom.setUser(userinfo);
        	ChatHistory chatHistory = new ChatHistory();
        	chatHistory.setAnswer(answer);
        	chatHistory.setQuestion(question);
        	chatHistory.setChatRoom(chatRoom);
        	chatHistoryRep.save(chatHistory);
        	chatRoomRep.save(chatRoom);
		}
		else {
			ChatRoom chatRoom = chatRoomRep.findChatRoomById(chatRoomId);
        	ChatHistory chatHistory = new ChatHistory();
        	chatHistory.setAnswer(answer);
        	chatHistory.setQuestion(question);
        	chatHistory.setChatRoom(chatRoom);
        	chatHistoryRep.save(chatHistory);
			
		}
        return ResponseEntity.ok(answer);
	}
	
//  방 이름 수정
	@PostMapping("/editroomname")
	public ResponseEntity<String> editRoomName(@AuthenticationPrincipal UD user, @RequestParam Long chatRoomId, @RequestParam String newName) {
		User userinfo = userservice.findByEmail(user.getEmail());
		ChatRoom chatRoom = chatRoomRep.findChatRoomById(chatRoomId);
		if (chatRoom.getUser().getId() != userinfo.getId()) {
			return ResponseEntity.status(403).body("Forbidden");
		}
		chatRoom.setName(newName);
		chatRoomRep.save(chatRoom);
		return ResponseEntity.ok("Room name updated successfully");
	}

	// 방 삭제
	@PostMapping("/deleteroom")
	public ResponseEntity<String> deleteRoom(@AuthenticationPrincipal UD user, @RequestParam Long chatRoomId) {
		User userinfo = userservice.findByEmail(user.getEmail());
		ChatRoom chatRoom = chatRoomRep.findChatRoomById(chatRoomId);
		if (chatRoom.getUser().getId() != userinfo.getId()) {
			return ResponseEntity.status(403).body("Forbidden");
		}
		chatHistoryRep.deleteAllByChatRoom(chatRoom);
		chatRoomRep.delete(chatRoom);
		return ResponseEntity.ok("Room deleted successfully");
	}
	
	// 전체 방 삭제
	@PostMapping("/deleteallrooms")
	public ResponseEntity<String> deleteAllRooms(@AuthenticationPrincipal UD user) {
		User userinfo = userservice.findByEmail(user.getEmail());
		List<ChatRoom> chatRooms = chatRoomRep.findAllByUser(userinfo);
		for (ChatRoom chatRoom : chatRooms) {
			chatHistoryRep.deleteAllByChatRoom(chatRoom);
			chatRoomRep.delete(chatRoom);
		}
		return ResponseEntity.ok("All rooms deleted successfully");
	}
}













