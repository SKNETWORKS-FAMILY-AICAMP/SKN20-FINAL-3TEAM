"""
챗봇 서비스
RAG 기반 평면도 관련 질의응답 + PostgreSQL 이전 대화 내역 활용
"""

import logging
import os
import re
from typing import Optional, Dict, Any, List
import psycopg2
from psycopg2.extras import RealDictCursor

from openai import OpenAI

from CV.rag_system.config import RAGConfig
from CV.rag_system.embeddings import EmbeddingManager
from services.pgvector_service import pgvector_service

logger = logging.getLogger("ChatbotService")


class ChatbotService:
    """RAG 기반 챗봇 서비스 + PostgreSQL 대화 내역 활용"""
    
    # PostgreSQL 연결 정보 (application.properties와 동일)
    DB_CONFIG = {
        "host": "localhost",
        "port": 5432,
        "database": "arae",
        "user": "postgres",
        "password": "1234"
    }
    
    def __init__(self):
        self.config: Optional[RAGConfig] = None
        self.embedding_manager: Optional[EmbeddingManager] = None
        self.openai_client: Optional[OpenAI] = None
        self.db_conn = None
    
    def load_components(self):
        """RAG 컴포넌트를 lazy loading 방식으로 로드"""
        if self.openai_client is not None:
            return
        
        logger.info("챗봇 컴포넌트 로딩 중...")
        
        try:
            self.config = RAGConfig()
            self.embedding_manager = EmbeddingManager(
                api_key=self.config.OPENAI_API_KEY,
                model="text-embedding-3-small"
            )
            self.openai_client = OpenAI(api_key=self.config.OPENAI_API_KEY)
            
            # PostgreSQL 연결
            self.db_conn = psycopg2.connect(**self.DB_CONFIG)
            logger.info("PostgreSQL 연결 완료")
            
            logger.info("챗봇 컴포넌트 로딩 완료!")
        except Exception as e:
            logger.error(f"챗봇 컴포넌트 로딩 실패: {e}")
            raise
    
    def get_recent_chat_history(self, email: str, limit: int = 5) -> List[Dict[str, str]]:
        """
        PostgreSQL에서 사용자의 최근 대화 내역 조회
        
        Args:
            email: 사용자 이메일
            limit: 가져올 대화 개수
            
        Returns:
            [{"question": str, "answer": str, "created_at": str}, ...]
        """
        if self.db_conn is None:
            logger.warning("PostgreSQL 연결 안됨. 이전 대화 내역 없이 진행")
            return []
        
        if email == "anonymous":
            # 익명 사용자는 대화 내역 없음
            return []
        
        try:
            query = """
            SELECT ch.question, ch.answer, ch.created_at
            FROM "chat_history" ch
            JOIN "chatroom" cr ON ch.chatroom_id = cr.id
            JOIN "users" u ON cr.user_id = u.id
            WHERE u.email = %s
            ORDER BY ch.created_at DESC
            LIMIT %s
            """
            
            with self.db_conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, (email, limit))
                results = cursor.fetchall()
                
                # 시간순으로 정렬 (오래된 것부터)
                history = [
                    {
                        "question": row["question"],
                        "answer": row["answer"],
                        "created_at": str(row["created_at"])
                    }
                    for row in reversed(results)
                ]
                
                logger.info(f"{email}의 이전 대화 {len(history)}개 조회 완료")
                return history
                
        except Exception as e:
            logger.error(f"대화 내역 조회 실패: {e}")
            return []
    
    def extract_region_codes(self, text: str) -> List[str]:
        """
        질문에서 구분코드 추출 (예: "11110", "41135" 등)
        
        Args:
            text: 질문 텍스트
            
        Returns:
            추출된 코드 리스트
        """
        # 5자리 숫자 패턴 추출
        codes = re.findall(r'\b\d{5}\b', text)
        return codes
    
    def get_law_info(self, region_codes: List[str]) -> List[Dict[str, Any]]:
        """
        Law 테이블에서 구분코드로 법률 정보 조회
        
        Args:
            region_codes: 지역 코드 리스트
            
        Returns:
            법률 정보 리스트
        """
        if self.db_conn is None:
            logger.warning("PostgreSQL 연결 안됨. 법률 정보 조회 불가")
            return []
        
        if not region_codes:
            return []
        
        try:
            query = """
            SELECT 
                region_code,
                zone_district_name,
                law_name,
                land_use_activity,
                permission_status,
                condition_exception
            FROM law
            WHERE region_code = ANY(%s)
            """
            
            with self.db_conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, (region_codes,))
                results = cursor.fetchall()
                
                law_infos = [
                    {
                        "region_code": row["region_code"],
                        "zone_district_name": row["zone_district_name"],
                        "law_name": row["law_name"],
                        "land_use_activity": row["land_use_activity"],
                        "permission_status": row["permission_status"],
                        "condition_exception": row["condition_exception"]
                    }
                    for row in results
                ]
                
                logger.info(f"법률 정보 {len(law_infos)}개 조회 완료 (코드: {region_codes})")
                return law_infos
                
        except Exception as e:
            logger.error(f"법률 정보 조회 실패: {e}")
            return []
    
    def ask(self, email: str, question: str) -> Dict[str, str]:
        """
        사용자 질문에 RAG 기반으로 답변
        
        Args:
            email: 사용자 이메일
            question: 질문
            
        Returns:
            {"summaryTitle": str, "answer": str}
        """
        self.load_components()
        
        try:
            logger.info(f"질문 받음: {email} - {question}")
            
            # 1. 질문에서 구분코드 추출 및 Law 정보 조회
            region_codes = self.extract_region_codes(question)
            law_infos = self.get_law_info(region_codes)
            
            # 2. 이전 대화 내역 조회 (PostgreSQL)
            chat_history = self.get_recent_chat_history(email, limit=5)
            
            # 3. 질문 임베딩
            question_embedding = self.embedding_manager.embed_text(question)
            
            # 3. RAG 검색 (pgvector 사용)
            rag_results = pgvector_service.search_internal_eval(
                query_embedding=question_embedding,
                k=3  # 상위 3개 결과
            )
            
            # 4. 컨텍스트 구성
            context_parts = []
            
            # 4-1. Law 정보 추가
            if law_infos:
                law_text_parts = []
                for law in law_infos:
                    law_text = (
                        f"지역코드: {law['region_code']}\n"
                        f"용도지역/지구명: {law['zone_district_name']}\n"
                        f"관련 법률: {law['law_name']}\n"
                        f"토지 이용 행위: {law['land_use_activity']}\n"
                        f"허가 상태: {law['permission_status']}\n"
                        f"조건 및 예외사항: {law['condition_exception']}"
                    )
                    law_text_parts.append(law_text)
                context_parts.append(f"[법률/규제 정보]\n" + "\n\n".join(law_text_parts) + "\n")
            
            # 4-2. 이전 대화 내역 추가
            if chat_history:
                history_text = "\n".join([
                    f"Q: {h['question']}\nA: {h['answer']}"
                    for h in chat_history
                ])
                context_parts.append(f"[이전 대화 내역]\n{history_text}\n")
            
            # 4-3. RAG 검색 결과 추가
            if rag_results:
                for i, result in enumerate(rag_results, 1):
                    context_parts.append(f"[참고 평면도 {i}]\n{result['document']}\n")
            
            context = "\n".join(context_parts) if context_parts else "참고할 데이터가 없습니다."
            
            # 6. LLM에게 질문 (GPT-4)
            messages = [
                {
                    "role": "system",
                    "content": (
                        "당신은 건축 평면도 및 부동산 법률 전문가입니다. "
                        "사용자의 질문에 포함된 지역 코드에 해당하는 법률/규제 정보, "
                        "이전 대화 내역, 평면도 분석 자료를 모두 참고하여 "
                        "친절하고 전문적으로 답변해주세요. "
                        "답변은 한국어로 작성하며, 법률적 제약사항, 평면도의 장단점, 개선 방안 등을 구체적으로 설명해주세요.\n\n"
                        f"[참고 자료]\n{context}"
                    )
                },
                {
                    "role": "user",
                    "content": question
                }
            ]
            
            response = self.openai_client.chat.completions.create(
                model=self.config.OPENAI_MODEL,
                messages=messages,
                temperature=0.7
            )
            
            answer = response.choices[0].message.content
            
            # 6. 요약 제목 생성 (간단하게)
            summary_title = question[:30] + "..." if len(question) > 30 else question
            
            logger.info(f"답변 생성 완료: {summary_title}")
            
            return {
                "summaryTitle": summary_title,
                "answer": answer
            }
            
        except Exception as e:
            logger.error(f"챗봇 답변 생성 실패: {e}")
            return {
                "summaryTitle": "오류 발생",
                "answer": f"답변 생성 중 오류가 발생했습니다: {str(e)}"
            }
    
    def is_loaded(self) -> bool:
        """컴포넌트 로드 여부 확인"""
        return self.openai_client is not None


# 싱글톤 인스턴스
chatbot_service = ChatbotService()
