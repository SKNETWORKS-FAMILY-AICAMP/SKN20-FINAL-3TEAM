package com.example.skn20.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.ResourceHandlerRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

/**
 * Web MVC 설정
 * Static Resource 경로 설정
 */
@Configuration
public class WebConfig implements WebMvcConfigurer {

    @Override
    public void addResourceHandlers(ResourceHandlerRegistry registry) {
        // /image/** 경로를 classpath:/image/ 디렉토리에 매핑
        registry
            .addResourceHandler("/image/**")
            .addResourceLocations("classpath:/image/");
    }
}
