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
            if self.db_conn:
                self.db_conn.rollback()
            return []
    
    def parse_address(self, text: str) -> Dict[str, str]:
        """질문에서 주소 정보 추출"""
        result = {"legal_dong_name": "", "lot_number": "", "region_code": ""}
        
        # 법정동명 추출 (시군구 + 동)
        dong_parts = []
        sigungu_match = re.search(r'([\w]+시|[\w]+군|[\w]+구)', text)
        if sigungu_match:
            dong_parts.append(sigungu_match.group(1))
        
        dong_match = re.search(r'([\w]+동|[\w]+읍|[\w]+면|[\w]+가)', text)
        if dong_match:
            dong_parts.append(dong_match.group(1))
        
        if dong_parts:
            result["legal_dong_name"] = ' '.join(dong_parts)
        
        # 지번 추출
        lot_match = re.search(r'(\d+-\d+|\d+번지)', text)
        if lot_match:
            result["lot_number"] = lot_match.group(1).replace('번지', '')
        
        # 지역코드 추출 (서울=11, 경기=41)
        if '서울' in text:
            result["region_code"] = '11'
        elif '경기' in text:
            result["region_code"] = '41'
        
        return result
    
    def extract_zone_district_name(self, text: str) -> List[str]:
        """질문에서 지역지구명 추출"""
        zone_patterns = [
            r'(제\d종[^\s]{2,10}지역)', r'([^\s]{2,10}경관지구)',
            r'([^\s]{2,10}미관지구)', r'([^\s]{2,10}녹지지역)',
            r'([^\s]{2,10}주거지역)', r'([^\s]{2,10}상업지역)',
            r'([^\s]{2,10}공업지역)', r'([^\s]{2,10}보호지구)',
            r'([^\s]{2,10}특화경관지구)',
        ]
        
        zones = []
        for pattern in zone_patterns:
            matches = re.findall(pattern, text)
            zones.extend(matches)
        
        return list(set(zones))
    
    def extract_land_use_activity(self, text: str) -> List[str]:
        """질문에서 토지이용행위 추출"""
        activities = []
        
        building_keywords = {
            '건물': '건축물', '미용실': '미용업', '공중화장실': '공중화장실',
            '철도시설': '철도시설', '가축사육': '가축사육시설', '층': '건축물',
        }
        
        for keyword, activity in building_keywords.items():
            if keyword in text:
                activities.append(activity)
        
        floor_match = re.search(r'(\d+)층', text)
        if floor_match:
            activities.append(f"{floor_match.group(1)}층 건축물")
        
        return list(set(activities))
    
    def extract_region_codes(self, text: str) -> List[str]:
        """질문에서 구분코드 추출"""
        codes = re.findall(r'\b\d{5}\b', text)
        return codes
    
    def search_by_address(self, address_info: Dict[str, str]) -> List[Dict[str, Any]]:
        """주소 정보로 land_char 테이블에서 검색"""
        if self.db_conn is None:
            return []
        
        try:
            conditions = []
            params = []
            
            if address_info.get("legal_dong_name"):
                conditions.append("legal_dong_name LIKE %s")
                params.append(f"%{address_info['legal_dong_name']}%")
            
            if address_info.get("lot_number"):
                conditions.append("lot_number = %s")
                params.append(address_info['lot_number'])
            
            if address_info.get("region_code"):
                conditions.append("region_code LIKE %s")
                params.append(f"{address_info['region_code']}%")
            
            if not conditions:
                return []
            
            query = f"""
            SELECT DISTINCT
                legal_dong_name, lot_number, region_code,
                zone1, zone2, land_category, land_use
            FROM land_char
            WHERE {' AND '.join(conditions)}
            LIMIT 20
            """
            
            with self.db_conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, params)
                results = cursor.fetchall()
                
                land_infos = [dict(row) for row in results]
                logger.info(f"주소 검색 결과: {len(land_infos)}개")
                return land_infos
                
        except Exception as e:
            logger.error(f"주소 검색 실패: {e}")
            if self.db_conn:
                self.db_conn.rollback()
            return []
    
    def search_by_zone_district(self, zone_names: List[str], region_filter: Dict[str, str] = None) -> List[Dict[str, Any]]:
        """지역지구명으로 law 테이블에서 검색 (유사도 기반)"""
        if self.db_conn is None or not zone_names:
            return []
        
        try:
            zone_conditions = []
            for zone in zone_names:
                zone_conditions.append(f"similarity(zone_district_name, '{zone}') > 0.3")
            
            where_clause = f"({' OR '.join(zone_conditions)})"
            
            if region_filter and region_filter.get("region_code"):
                where_clause += f" AND region_code LIKE '{region_filter['region_code']}%'"
            
            query = f"""
            SELECT DISTINCT
                region_code, zone_district_name, law_name,
                land_use_activity, permission_status, condition_exception
            FROM law
            WHERE {where_clause}
            ORDER BY zone_district_name
            LIMIT 50
            """
            
            with self.db_conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query)
                results = cursor.fetchall()
                
                law_infos = [dict(row) for row in results]
                logger.info(f"지역지구명 검색 결과: {len(law_infos)}개")
                return law_infos
                
        except Exception as e:
            logger.error(f"지역지구명 검색 실패: {e}")
            if self.db_conn:
                self.db_conn.rollback()
            return []
    
    def search_by_land_use(self, activities: List[str], zone_name: str = None, region_filter: Dict[str, str] = None) -> List[Dict[str, Any]]:
        """토지이용행위로 law 테이블에서 검색"""
        if self.db_conn is None or not activities:
            return []
        
        try:
            conditions = []
            
            activity_conditions = []
            for activity in activities:
                activity_conditions.append(f"land_use_activity LIKE '%{activity}%'")
            conditions.append(f"({' OR '.join(activity_conditions)})")
            
            if zone_name:
                conditions.append(f"similarity(zone_district_name, '{zone_name}') > 0.3")
            
            if region_filter and region_filter.get("region_code"):
                conditions.append(f"region_code LIKE '{region_filter['region_code']}%'")
            
            query = f"""
            SELECT DISTINCT
                region_code, zone_district_name, law_name,
                land_use_activity, permission_status, condition_exception
            FROM law
            WHERE {' AND '.join(conditions)}
            LIMIT 50
            """
            
            with self.db_conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query)
                results = cursor.fetchall()
                
                law_infos = [dict(row) for row in results]
                logger.info(f"토지이용행위 검색 결과: {len(law_infos)}개")
                return law_infos
                
        except Exception as e:
            logger.error(f"토지이용행위 검색 실패: {e}")
            if self.db_conn:
                self.db_conn.rollback()
            return []
    
    def get_zones_by_region(self, region_filter: Dict[str, str]) -> List[str]:
        """특정 지역의 지역지구명 목록 조회"""
        if self.db_conn is None:
            return []
        
        try:
            if not region_filter.get("region_code"):
                return []
            
            query = """
            SELECT DISTINCT zone_district_name
            FROM law
            WHERE region_code LIKE %s
            ORDER BY zone_district_name
            """
            
            with self.db_conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, (f"{region_filter['region_code']}%",))
                results = cursor.fetchall()
                
                zones = [row['zone_district_name'] for row in results]
                logger.info(f"지역 내 지역지구명 {len(zones)}개 조회")
                return zones
                
        except Exception as e:
            logger.error(f"지역지구명 목록 조회 실패: {e}")
            if self.db_conn:
                self.db_conn.rollback()
            return []
    
    def get_law_info(self, region_codes: List[str]) -> List[Dict[str, Any]]:
        """Law 테이블에서 구분코드로 법률 정보 조회"""
        if self.db_conn is None:
            logger.warning("PostgreSQL 연결 안됨")
            return []
        
        if not region_codes:
            return []
        
        try:
            query = """
            SELECT 
                region_code, zone_district_name, law_name,
                land_use_activity, permission_status, condition_exception
            FROM law
            WHERE region_code = ANY(%s)
            """
            
            with self.db_conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, (region_codes,))
                results = cursor.fetchall()
                
                law_infos = [dict(row) for row in results]
                logger.info(f"법률 정보 {len(law_infos)}개 조회 완료")
                return law_infos
                
        except Exception as e:
            logger.error(f"법률 정보 조회 실패: {e}")
            if self.db_conn:
                self.db_conn.rollback()
            return []
    
    def ask(self, email: str, question: str) -> Dict[str, str]:
        """사용자 질문에 RAG 기반으로 답변"""
        self.load_components()
        
        try:
            logger.info(f"질문 받음: {email} - {question}")
            
            # 1. 질문 분석
            address_info = self.parse_address(question)
            zone_names = self.extract_zone_district_name(question)
            activities = self.extract_land_use_activity(question)
            region_codes = self.extract_region_codes(question)
            
            logger.info(f"분석 - 주소: {address_info}, 지역지구: {zone_names}, 행위: {activities}, 코드: {region_codes}")
            
            # 2. 지역 필터
            region_filter = {}
            if address_info.get("region_code"):
                region_filter["region_code"] = address_info["region_code"]
            
            # 3. 다양한 검색
            all_results = []
            
            if any(address_info.values()):
                land_results = self.search_by_address(address_info)
                if land_results:
                    all_results.append(("토지 정보", land_results))
            
            if region_codes:
                code_results = self.get_law_info(region_codes)
                if code_results:
                    all_results.append(("법률 정보 (코드)", code_results))
            
            if zone_names:
                zone_results = self.search_by_zone_district(zone_names, region_filter)
                if zone_results:
                    all_results.append(("법률 정보 (지역지구)", zone_results))
            
            if activities:
                activity_results = self.search_by_land_use(
                    activities, 
                    zone_names[0] if zone_names else None,
                    region_filter
                )
                if activity_results:
                    all_results.append(("법률 정보 (토지이용)", activity_results))
            
            if ("어떤" in question or "목록" in question or "있어" in question) and region_filter and not zone_names:
                zone_list = self.get_zones_by_region(region_filter)
                if zone_list:
                    all_results.append(("지역지구명 목록", zone_list))
            
            # 4. 이전 대화
            chat_history = self.get_recent_chat_history(email, limit=5)
            
            # 5. RAG 검색
            question_embedding = self.embedding_manager.embed_text(question)
            rag_results = pgvector_service.search_internal_eval(
                query_embedding=question_embedding,
                k=3
            )
            
            # 6. 컨텍스트 구성
            context_parts = []
            
            for title, results in all_results:
                if isinstance(results, list) and results:
                    if isinstance(results[0], str):
                        context_parts.append(f"[{title}]\n" + ", ".join(results[:50]) + "\n")
                    elif isinstance(results[0], dict):
                        result_texts = []
                        for item in results[:10]:
                            if 'zone1' in item:
                                text = (
                                    f"주소: {item.get('legal_dong_name', '')} {item.get('lot_number', '')}\n"
                                    f"용도지역: {item.get('zone1', '')}, {item.get('zone2', '')}\n"
                                    f"토지분류: {item.get('land_category', '')}, 토지용도: {item.get('land_use', '')}"
                                )
                            else:
                                text = (
                                    f"지역코드: {item.get('region_code', '')} / 지역지구: {item.get('zone_district_name', '')}\n"
                                    f"관련 법률: {item.get('law_name', '')}\n"
                                    f"토지이용행위: {item.get('land_use_activity', '')}\n"
                                    f"허가상태: {item.get('permission_status', '')}\n"
                                    f"조건/예외: {item.get('condition_exception', '')}"
                                )
                            result_texts.append(text)
                        context_parts.append(f"[{title}]\n" + "\n\n".join(result_texts) + "\n")
            
            if chat_history:
                history_text = "\n".join([
                    f"Q: {h['question']}\nA: {h['answer']}"
                    for h in chat_history[:3]
                ])
                context_parts.append(f"[이전 대화]\n{history_text}\n")
            
            if rag_results:
                for i, result in enumerate(rag_results, 1):
                    context_parts.append(f"[참고 평면도 {i}]\n{result['document']}\n")
            
            context = "\n".join(context_parts) if context_parts else "참고할 데이터가 없습니다."
            
            # 7. LLM 질문
            messages = [
                {
                    "role": "system",
                    "content": (
                        "당신은 건축 평면도 및 부동산 법률 전문가입니다.\n\n"
                        "**중요 지침:**\n"
                        "1. 반드시 아래 [참고 자료]에 포함된 정보만을 사용하여 답변하세요.\n"
                        "2. [참고 자료]에 없는 내용은 절대 답변하지 마세요.\n"
                        "3. 질문에 대한 답변이 [참고 자료]에 없다면, '제공된 자료에서 해당 정보를 찾을 수 없습니다'라고 명확히 답변하세요.\n"
                        "4. 외부 지식이나 일반적인 상식을 사용하지 말고, 오직 제공된 자료만 참고하세요.\n"
                        "5. 답변 시 어떤 자료(토지 정보, 법률 정보, 이전 대화 등)를 참고했는지 명시하세요.\n\n"
                        "답변은 한국어로 작성하며, 법률적 제약사항, 평면도의 장단점, 개선 방안 등을 "
                        "[참고 자료]에 기반하여 구체적으로 설명해주세요.\n\n"
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
                temperature=0.3  # 낮은 temperature로 더 보수적이고 정확한 답변 유도
            )
            
            answer = response.choices[0].message.content
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
