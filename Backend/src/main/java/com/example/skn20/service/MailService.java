package com.example.skn20.service;

import java.time.LocalDateTime;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.logging.Logger;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.mail.javamail.JavaMailSender;
import org.springframework.scheduling.annotation.Async;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

import jakarta.mail.MessagingException;
import jakarta.mail.internet.MimeMessage;
import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.RequiredArgsConstructor;

@Service
@RequiredArgsConstructor
public class MailService {

    private static final Logger logger = Logger.getLogger(MailService.class.getName());
    private final JavaMailSender javaMailSender;
    
    @Value("${mail.sender:3179954@gmail.com}")
    private String senderEmail;
    
    private final Map<String, VerificationData> emailVerificationMap = new ConcurrentHashMap<>();
    private final Map<String, LocalDateTime> lastSentMap = new ConcurrentHashMap<>();

    @Async
    public void sendMail(String mail) {
        // 재전송 제한 체크 (30초)
        LocalDateTime lastSent = lastSentMap.get(mail);
        if (lastSent != null && lastSent.plusSeconds(30).isAfter(LocalDateTime.now())) {
            throw new RuntimeException("30초 후에 재시도해주세요.");
        }
        
        int number = createNumber();
        MimeMessage message = javaMailSender.createMimeMessage();
        try {
            message.setFrom(senderEmail);
            message.setRecipients(MimeMessage.RecipientType.TO, mail);
            message.setSubject("ARAE에서 보낸 인증 번호입니다. : " + number);
            message.setText(buildEmailBody(number), "UTF-8", "html");

            javaMailSender.send(message);
            emailVerificationMap.put(mail, new VerificationData(number, LocalDateTime.now()));
            lastSentMap.put(mail, LocalDateTime.now());
            logger.info("인증번호 " + number + "가 " + mail + " 이메일로 전송되었습니다.");
            System.out.println("인증번호 " + number + "가 " + mail + " 이메일로 전송되었습니다.");

        } catch (MessagingException e) {
            e.printStackTrace();
            throw new RuntimeException("메일 전송에 실패했습니다.", e);
        }
    }

    public int getVerificationNumber(String mail) {
        VerificationData data = emailVerificationMap.get(mail);
        return data != null ? data.getCode() : -1;
    }

    private int createNumber() {
        return (int) (Math.random() * 900000) + 100000;
    }

    public boolean checkVerificationNumber(String mail, int userNumber) {
        VerificationData data = emailVerificationMap.get(mail);
        
        if (data == null) {
            return false;
        }
        
        // 5분 만료 체크
        if (data.getCreatedAt().plusMinutes(5).isBefore(LocalDateTime.now())) {
            emailVerificationMap.remove(mail);
            logger.info("만료된 인증번호: " + mail);
            return false;
        }
        
        // 인증 성공 시 데이터 삭제
        if (data.getCode() == userNumber) {
            emailVerificationMap.remove(mail);
            lastSentMap.remove(mail);
            logger.info("인증 성공: " + mail);
            return true;
        }
        
        return false;
    }
    
    // 10분마다 만료된 인증번호 자동 정리
    @Scheduled(fixedRate = 600000)
    public void cleanupExpiredCodes() {
        LocalDateTime now = LocalDateTime.now();
        
        long removedCount = emailVerificationMap.entrySet().stream()
            .filter(entry -> entry.getValue().getCreatedAt().plusMinutes(5).isBefore(now))
            .peek(entry -> emailVerificationMap.remove(entry.getKey()))
            .count();
        
        if (removedCount > 0) {
            logger.info("만료된 인증번호 " + removedCount + "개 정리 완료");
        }
    }
    
    @Getter
    @AllArgsConstructor
    private static class VerificationData {
        private final int code;
        private final LocalDateTime createdAt;
    }

    private String buildEmailBody(int number) {
        String code = String.valueOf(number);
        // 인증코드 각 자리를 개별 박스로 분리
        StringBuilder codeBoxes = new StringBuilder();
        for (char c : code.toCharArray()) {
            codeBoxes.append("<td style='width:48px;height:56px;background-color:#FFF7ED;border:2px solid #FF8C42;border-radius:10px;font-size:28px;font-weight:700;color:#FF8C42;text-align:center;vertical-align:middle;font-family:monospace;'>");
            codeBoxes.append(c);
            codeBoxes.append("</td><td style='width:6px;'></td>");
        }

        return "<!DOCTYPE html>"
             + "<html lang='ko'>"
             + "<head>"
             + "<meta charset='UTF-8'>"
             + "<meta name='viewport' content='width=device-width, initial-scale=1.0'>"
             + "</head>"
             + "<body style='margin:0;padding:0;background-color:#F3F4F6;font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;'>"
             + "<table role='presentation' width='100%' cellpadding='0' cellspacing='0' style='background-color:#F3F4F6;padding:40px 20px;'>"
             + "<tr><td align='center'>"
             + "<table role='presentation' width='480' cellpadding='0' cellspacing='0' style='background-color:#FFFFFF;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);'>"

             // 상단 오렌지 헤더
             + "<tr><td style='background:linear-gradient(135deg,#FF8C42,#FF7A2E);padding:32px 40px;text-align:center;'>"
             + "<h1 style='margin:0;font-size:28px;font-weight:800;color:#FFFFFF;letter-spacing:3px;'>ARAE</h1>"
             + "<p style='margin:6px 0 0;font-size:13px;color:rgba(255,255,255,0.85);letter-spacing:1px;'>AI Floor Plan Analysis Platform</p>"
             + "</td></tr>"

             // 본문
             + "<tr><td style='padding:36px 40px 20px;'>"
             + "<h2 style='margin:0 0 8px;font-size:20px;font-weight:700;color:#1F2937;text-align:center;'>이메일 인증</h2>"
             + "<p style='margin:0 0 28px;font-size:14px;color:#6B7280;line-height:1.7;text-align:center;'>"
             + "회원님의 이메일 주소 확인을 위한 인증번호입니다.<br>"
             + "아래 인증번호를 입력하여 인증을 완료해 주세요.</p>"

             // 인증코드 박스
             + "<table role='presentation' cellpadding='0' cellspacing='0' style='margin:0 auto 28px;'>"
             + "<tr>" + codeBoxes.toString() + "</tr>"
             + "</table>"

             // 유효시간 안내
             + "<table role='presentation' width='100%' cellpadding='0' cellspacing='0'>"
             + "<tr><td style='background-color:#FFF7ED;border-radius:10px;padding:14px 20px;text-align:center;'>"
             + "<span style='font-size:13px;color:#FF8C42;'>&#9202;</span>"
             + "<span style='font-size:13px;color:#92400E;font-weight:500;'> 인증번호는 <b>5분</b> 동안만 유효합니다</span>"
             + "</td></tr></table>"
             + "</td></tr>"

             // 구분선
             + "<tr><td style='padding:0 40px;'>"
             + "<hr style='border:none;border-top:1px solid #E5E7EB;margin:12px 0 0;'>"
             + "</td></tr>"

             // 푸터
             + "<tr><td style='padding:20px 40px 32px;text-align:center;'>"
             + "<p style='margin:0 0 4px;font-size:11px;color:#9CA3AF;'>본 메일은 ARAE 서비스에서 자동 발송된 메일입니다.</p>"
             + "<p style='margin:0;font-size:11px;color:#9CA3AF;'>본인이 요청하지 않았다면 이 메일을 무시해 주세요.</p>"
             + "</td></tr>"

             + "</table>"
             + "</td></tr></table>"
             + "</body></html>";
    }

}
