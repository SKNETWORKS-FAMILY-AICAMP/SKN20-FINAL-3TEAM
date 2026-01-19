package com.example.skn20.controller;

import com.example.skn20.classes.UserDetailsImpl;
import com.example.skn20.entity.User;
import com.example.skn20.security.JwtUtil;
import com.example.skn20.service.UserService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDate;
import java.util.HashMap;
import java.util.Map;

@RestController
@RequestMapping("/api/auth")
@RequiredArgsConstructor
@CrossOrigin(origins = { "http://localhost:3000", "http://localhost:5173" })
public class AuthController {

    private final AuthenticationManager authenticationManager;
    private final UserService userService;
    private final JwtUtil jwtUtil;

    // 이메일 중복 검사
    @PostMapping("/check-email")
    public ResponseEntity<String> checkEmail(@RequestParam String email) {
        try {
            User user = userService.findByEmail(email);
            if (user != null) {
                return ResponseEntity.status(HttpStatus.CONFLICT)
                        .body("이미 존재하는 이메일입니다.");
            }
            return ResponseEntity.ok("사용 가능한 이메일입니다.");
        } catch (Exception e) {
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .body("오류가 발생했습니다.");
        }
    }

    // 회원가입
    @PostMapping("/signup")
    public ResponseEntity<ApiResponse> signup(@RequestParam String email, @RequestParam String pw, @RequestParam String name, @RequestParam Integer phonenumber) {
        try {
            userService.registerUser(email, pw, name, phonenumber);
            return ResponseEntity.ok(new ApiResponse(true, "회원가입 성공"));
        } catch (RuntimeException e) {
            return ResponseEntity.status(HttpStatus.CONFLICT)
                    .body(new ApiResponse(false, e.getMessage()));
        } catch (Exception e) {
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .body(new ApiResponse(false, "회원가입 중 오류가 발생했습니다."));
        }
    }

    // 로그인
    @PostMapping("/login")
    public ResponseEntity<?> login(@RequestParam String email, @RequestParam String password) {
        try {
            Authentication authentication = authenticationManager.authenticate(
                    new UsernamePasswordAuthenticationToken(email, password));

            UD userDetails = (UD) authentication.getPrincipal();
            String jwt = jwtUtil.generateToken(userDetails);

            User user = userService.findByEmail(userDetails.getEmail());

            Map<String, Object> response = new HashMap<>();
            response.put("token", jwt);
            response.put("type", "Bearer");
            response.put("email", user.getEmail());
            response.put("username", user.getName());
            response.put("role", user.getRole());

            return ResponseEntity.ok(response);
        } catch (Exception e) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED)
                    .body(new ApiResponse(false, "이메일 또는 비밀번호가 올바르지 않습니다."));
        }
    }

    // 프로필 설정
    @PostMapping("/profile")
    public ResponseEntity<ApiResponse> setProfile(
            @RequestParam String name,
            @RequestParam Integer phonenumber,
            @AuthenticationPrincipal UD userDetails) {
        try {
            userService.updateProfile(userDetails.getEmail(), name, phonenumber);
            return ResponseEntity.ok(new ApiResponse(true, "프로필 수정 완료"));
        } catch (Exception e) {
            return ResponseEntity.badRequest()
                    .body(new ApiResponse(false, "프로필 수정 중 오류가 발생했습니다."));
        }
    }

    // 비밀번호 변경
    @PostMapping("/change-password")
    public ResponseEntity<ApiResponse> changePassword(
            @RequestParam String email,
            @RequestParam String newPassword) {
        try {
            userService.changePassword(email, newPassword);
            return ResponseEntity.ok(new ApiResponse(true, "비밀번호가 변경되었습니다."));
        } catch (Exception e) {
            return ResponseEntity.badRequest()
                    .body(new ApiResponse(false, "비밀번호 변경 중 오류가 발생했습니다."));
        }
    }

    // 현재 사용자 정보 조회
    @GetMapping("/me")
    public ResponseEntity<?> getCurrentUser(@AuthenticationPrincipal UD userDetails) {
        if (userDetails == null) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED)
                    .body(new ApiResponse(false, "인증이 필요합니다."));
        }

        User user = userService.findByEmail(userDetails.getEmail());
        return ResponseEntity.ok(user);
    }

    // 응답 DTO
    public record ApiResponse(boolean success, String message, String code) {
        public ApiResponse(boolean success, String message) {
            this(success, message, null);
        }
    }
}
