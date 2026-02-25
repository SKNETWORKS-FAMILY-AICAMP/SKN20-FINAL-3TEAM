package com.example.skn20.security;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.stereotype.Component;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.util.Date;
import java.util.HashMap;
import java.util.Map;
import java.util.function.Function;

@Component
public class JwtUtil {

    @Value("${jwt.secret}")
    private String secret;

    @Value("${jwt.expiration}")
    private Long expiration;

    private SecretKey getSigningKey() {
        return Keys.hmacShaKeyFor(secret.getBytes(StandardCharsets.UTF_8));
    }

    public String extractUsername(String token) {
        return extractClaim(token, Claims::getSubject);
    }

    public Date extractExpiration(String token) {
        return extractClaim(token, Claims::getExpiration);
    }

    public <T> T extractClaim(String token, Function<Claims, T> claimsResolver) {
        final Claims claims = extractAllClaims(token);
        return claimsResolver.apply(claims);
    }

    private Claims extractAllClaims(String token) {
        return Jwts.parser()
                .verifyWith(getSigningKey())
                .build()
                .parseSignedClaims(token)
                .getPayload();
    }

    private Boolean isTokenExpired(String token) {
        return extractExpiration(token).before(new Date());
    }

    public String generateToken(UserDetails userDetails, boolean rememberMe) {
        Map<String, Object> claims = new HashMap<>();
        claims.put("rememberMe", rememberMe);
        // rememberMe: 24시간, 아니면: 1시간
        long tokenExpiration = rememberMe ? 24 * 60 * 60 * 1000L : 60 * 60 * 1000L;
        return createToken(claims, userDetails.getUsername(), tokenExpiration);
    }

    /**
     * 토큰 갱신: 기존 토큰의 rememberMe 설정을 유지하며 새 토큰 발급
     */
    public String refreshToken(String token, UserDetails userDetails) {
        Claims claims = extractAllClaims(token);
        Boolean rememberMe = claims.get("rememberMe", Boolean.class);
        if (rememberMe == null) rememberMe = false;
        return generateToken(userDetails, rememberMe);
    }

    /**
     * 토큰 만료까지 남은 시간(ms) 반환
     */
    public long getTimeUntilExpiration(String token) {
        Date expiration = extractExpiration(token);
        return expiration.getTime() - System.currentTimeMillis();
    }

    private String createToken(Map<String, Object> claims, String subject, long tokenExpiration) {
        return Jwts.builder()
                .claims(claims)
                .subject(subject)
                .issuedAt(new Date(System.currentTimeMillis()))
                .expiration(new Date(System.currentTimeMillis() + tokenExpiration))
                .signWith(getSigningKey(), Jwts.SIG.HS256)
                .compact();
    }

    public Boolean validateToken(String token, UserDetails userDetails) {
        final String username = extractUsername(token);
        return (username.equals(userDetails.getUsername()) && !isTokenExpired(token));
    }
}
