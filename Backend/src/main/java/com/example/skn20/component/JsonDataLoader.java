package com.example.skn20.component;

import java.io.IOException;
import java.io.InputStream;
import java.util.List;

import org.springframework.boot.CommandLineRunner;
import org.springframework.core.io.ClassPathResource;
import org.springframework.stereotype.Component;

import com.example.skn20.entity.InternalEval;
import com.example.skn20.entity.LegalDocuments;
import com.example.skn20.repository.InternalEvalRepository;
import com.example.skn20.repository.LegalDocumentsRepository;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;

import lombok.RequiredArgsConstructor;

//@Component
@RequiredArgsConstructor
public class JsonDataLoader implements CommandLineRunner {

    private final LegalDocumentsRepository  legalRepository;
    private final InternalEvalRepository evalRepository;
    private final ObjectMapper objectMapper;

    @Override
    public void run(String... args) throws Exception {
        // 1. 법규 데이터 중복 체크 및 로드
        if (legalRepository.count() == 0) {
            loadLegalData("json/legal_docs.json");
        } else {
            System.out.println("법규 데이터가 이미 존재합니다. 로딩을 건너뜁니다.");
        }
        
        // 2. 내부 평가 데이터 중복 체크 및 로드
        if (evalRepository.count() == 0) {
            loadEvalData("json/internal_eval.json");
        } else {
            System.out.println("내부 평가 데이터가 이미 존재합니다. 로딩을 건너뜁니다.");
        }
    }

    private void loadLegalData(String fileName) throws IOException {
        InputStream  is = new ClassPathResource(fileName).getInputStream();
        List<LegalDocuments> docs = objectMapper.readValue(is, new TypeReference<>() {});
        legalRepository.saveAll(docs);
        System.out.println("법규 데이터 " + docs.size() + "건 저장 완료!");
    }

    private void loadEvalData(String fileName) throws IOException {
        InputStream is = new ClassPathResource(fileName).getInputStream();
        List<InternalEval> evals = objectMapper.readValue(is, new TypeReference<>() {});
        evalRepository.saveAll(evals);
        System.out.println("내부 평가 데이터 " + evals.size() + "건 저장 완료!");
    }
}