package com.example.skn20.config;

import org.springframework.boot.web.client.RestTemplateBuilder;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.web.client.RestTemplate;

import java.time.Duration;

@Configuration
public class RestTemplateConfig {

    @Bean
    public RestTemplate restTemplate(RestTemplateBuilder builder) {
        // Python CV 모델 로딩 및 분석 시간을 고려한 타임아웃 설정
        return builder
                .setConnectTimeout(Duration.ofSeconds(30))  // 연결 타임아웃: 30초
                .setReadTimeout(Duration.ofMinutes(5))      // 읽기 타임아웃: 5분 (CV 처리 시간)
                .build();
    }
}