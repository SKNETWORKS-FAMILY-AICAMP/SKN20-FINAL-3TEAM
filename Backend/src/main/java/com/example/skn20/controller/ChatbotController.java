package com.example.skn20.controller;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

import com.fasterxml.jackson.databind.ObjectMapper;

import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.CrossOrigin;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

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
@CrossOrigin(origins = { "http://localhost:3000", "http://localhost:8000", "http://43.200.42.14:3000" })
public class ChatbotController {

	private final UserService userservice;
	
	private final ChatbotService chatbotService;
	
	private final ChatRoomRepository chatRoomRep;
	
	private final ChatHistoryRepository chatHistoryRep;
	
//	웹 페이지 접속시 해당 유저의 채팅 history를 가져옵니다
	@PostMapping("/sessionuser")
	public ResponseEntity<List<ChatRoom>> SesstoinUser(@AuthenticationPrincipal UD user) {
		User userinfo = userservice.findByEmail(user.getEmail());
		List<ChatRoom> chatRooms = chatRoomRep.findAllByUserOrderByCreatedAtDesc(userinfo);

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
	public ResponseEntity<Map<String, Object>> question2answer(
	        @AuthenticationPrincipal UD user,
	        @RequestParam(required = false) Long chatRoomId,
	        @RequestParam String question,
	        @RequestParam(required = false) MultipartFile image  // 추가
	) {

	    // 인증되지 않은 사용자
		    if (user == null) {
		        Map<String, Object> result;
		        if (image != null && !image.isEmpty()) {
		            result = chatbotService.question2answerWithImage(null, question, image, chatRoomId);
		        } else {
		            result = chatbotService.question2answer(null, question, chatRoomId);
		        }
	        String answer = (String) result.get("answer");
	        Map<String, Object> response = new HashMap<>();
	        response.put("answer", answer);
	        return ResponseEntity.ok(response);
	    }

	    User userinfo = userservice.findByEmail(user.getEmail());

	    // 이미지 유무에 따라 분기
	    Map<String, Object> result;
	    if (image != null && !image.isEmpty()) {
	        result = chatbotService.question2answerWithImage(userinfo, question, image, chatRoomId);
	    } else {
	        result = chatbotService.question2answer(userinfo, question, chatRoomId);
	    }

	    String answer = (String) result.get("answer");

	    // image_urls를 JSON 문자열로 변환
	    String imageUrlsJson = null;
	    List<?> imageUrls = (List<?>) result.get("image_urls");
	    if (imageUrls != null && !imageUrls.isEmpty()) {
	        try {
	            imageUrlsJson = new ObjectMapper().writeValueAsString(imageUrls);
	        } catch (Exception e) {
	            // JSON 직렬화 실패 시 무시
	        }
	    }

	    Long responseChatRoomId = chatRoomId;

	    if (chatRoomId == null) {
	        // 새 채팅방 생성
	        ChatRoom chatRoom = new ChatRoom();
	        chatRoom.setName((String) result.get("summaryTitle"));
	        chatRoom.setUser(userinfo);
	        chatRoomRep.save(chatRoom);
	        responseChatRoomId = chatRoom.getId();

	        ChatHistory chatHistory = new ChatHistory();
	        chatHistory.setAnswer(answer);
	        chatHistory.setQuestion(question);
	        chatHistory.setImageUrls(imageUrlsJson);
	        chatHistory.setChatRoom(chatRoom);
	        chatHistoryRep.save(chatHistory);
	    } else {
	        // 기존 채팅방에 히스토리 추가
	        ChatRoom chatRoom = chatRoomRep.findChatRoomById(chatRoomId);
	        ChatHistory chatHistory = new ChatHistory();
	        chatHistory.setAnswer(answer);
	        chatHistory.setQuestion(question);
	        chatHistory.setImageUrls(imageUrlsJson);
	        chatHistory.setChatRoom(chatRoom);
	        chatHistoryRep.save(chatHistory);
	    }
	    
	    Map<String, Object> response = new HashMap<>();
	    response.put("answer", answer);
	    response.put("chatRoomId", responseChatRoomId);
	    response.put("image_urls", result.get("image_urls"));
	    return ResponseEntity.ok(response);
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
	@Transactional
	public ResponseEntity<String> deleteRoom(@AuthenticationPrincipal UD user, @RequestParam Long chatRoomId) {
		User userinfo = userservice.findByEmail(user.getEmail());
		ChatRoom chatRoom = chatRoomRep.findChatRoomById(chatRoomId);
		if (chatRoom == null) {
			return ResponseEntity.status(404).body("ChatRoom not found");
		}
		
		if (chatRoom.getUser() == null || chatRoom.getUser().getId() != userinfo.getId()) {
			return ResponseEntity.status(403).body("Forbidden");
		}
		
		chatHistoryRep.deleteAllByChatRoom(chatRoom);
		chatRoomRep.delete(chatRoom);
		return ResponseEntity.ok("Room deleted successfully");
	}
	
	// 전체 방 삭제
	@PostMapping("/deleteallrooms")
	@Transactional
	public ResponseEntity<String> deleteAllRooms(@AuthenticationPrincipal UD user) {
		User userinfo = userservice.findByEmail(user.getEmail());
		List<ChatRoom> chatRooms = chatRoomRep.findAllByUserOrderByCreatedAtDesc(userinfo);
		for (ChatRoom chatRoom : chatRooms) {
			chatHistoryRep.deleteAllByChatRoom(chatRoom);
			chatRoomRep.delete(chatRoom);
		}
		return ResponseEntity.ok("All rooms deleted successfully");
	}
}












