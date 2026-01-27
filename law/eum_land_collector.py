"""
토지이음(eum.go.kr) 데이터 수집기
- 토지이용계획 (건폐율, 용적률, 용도지역 등)
- 공시지가
- 행위제한 및 규제법령 (높이제한 등)
- 행위제한내용 (건축 가능/불가 건축물, 용도지역별 제한)
- 법령 조문 전문 조회 (law.go.kr 웹 스크래핑)

=== 수집 엔드포인트 ===
- luLandDetUseGYAjax.jsp (carGbn=GY) : 건폐율/용적률
- luLandDetUseCAjax.jsp (carGbn=C)   : 규제법령 (높이제한 등)
- luLandDetUseKDAjax.jsp (carGbn=K)  : 행위제한내용 (건축 가능/불가)
- luLandDetUseKDAjax.jsp (carGbn=K2) : 행위제한내용 상세
- lwLawDetContentsAjax.jsp (carGbn=all) : 용도지역별 법령 상세
  - carGbn=0: 행위제한
  - carGbn=1: 건폐율
  - carGbn=2: 용적률
  - carGbn=4: 건축/도로조건
  - carGbn=all: 전체

=== 설치 ===
    pip install requests

=== 실행 ===
    python eum_land_collector.py

=== 출력 ===
    land_info_{PNU}.json

=== 코드에서 임포트 ===
    from eum_land_collector import EumLandCollector

    collector = EumLandCollector()
    results = collector.search_address("서울 강남구 강남대로 382")
    land_data = collector.get_full_land_info(results[0]['pnu'], include_full_text=True)
"""

import requests
import re
import json
import xml.etree.ElementTree as ET
from typing import List, Dict, Optional


class EumLandCollector:
    def __init__(self, law_oc: str = None):
        """
        토지이음 데이터 수집기 초기화

        Args:
            law_oc: 국가법령정보센터 API OC (사용자 ID)
                    open.law.go.kr 가입 시 발급됨
                    예: "fodnjs15"
        """
        self.session = requests.Session()
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "*/*",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": "https://www.eum.go.kr/web/ar/lu/luLandDet.jsp"
        }
        self.law_oc = law_oc
        self._law_cache = {}  # 조문 캐싱: {"건축법_제60조": "제60조(건축물의 높이 제한)..."}
        self._init_session()

    def _init_session(self):
        """세션 초기화 (쿠키 생성)"""
        self.session.get("https://www.eum.go.kr/web/am/amMain.jsp")
        self.session.get("https://www.eum.go.kr/web/ar/lu/luLandDet.jsp", headers=self.headers)
        print("[세션] 초기화 완료")

    def search_law_by_name(self, law_name: str) -> Optional[Dict]:
        """
        법령명으로 법령 정보 조회 (국가법령정보센터 API)

        Args:
            law_name: 법령명 (예: "건축법", "국토의 계획 및 이용에 관한 법률")

        Returns:
            {"법령ID": "...", "법령명정식": "...", "조문목록": [...]} 또는 None
        """
        if not self.law_oc:
            return None

        url = "http://www.law.go.kr/DRF/lawSearch.do"
        params = {
            "OC": self.law_oc,
            "target": "law",
            "type": "XML",
            "query": law_name,
            "display": "5"
        }

        try:
            res = self.session.get(url, params=params, timeout=20)
            res.encoding = 'utf-8'

            # XML 파싱
            root = ET.fromstring(res.text)

            # 첫 번째 법령 정보 추출
            law = root.find('.//law')
            if law is None:
                print(f"[법령검색] '{law_name}' 검색 결과 없음")
                return None

            law_id = law.findtext('법령ID', '')
            law_name_official = law.findtext('법령명한글', '')

            result = {
                "법령ID": law_id,
                "법령명정식": law_name_official,
            }

            print(f"[법령검색] '{law_name}' → {law_name_official} (ID: {law_id})")
            return result

        except Exception as e:
            print(f"[법령검색] 오류: {e}")
            return None

    def get_law_article_text(self, law_name: str, article_num: str) -> Optional[str]:
        """
        법령명 + 조번호로 조문 전문 조회 (law.go.kr 웹 스크래핑)
        국가법령 및 지방자치법규(조례) 모두 지원

        Args:
            law_name: 법령명 (예: "건축법", "서울특별시 건축 조례")
            article_num: 조항 (예: "제60조", "제33조")

        Returns:
            조문 전문 텍스트 또는 None
        """
        # 캐시 확인
        cache_key = f"{law_name}_{article_num}"
        if cache_key in self._law_cache:
            print(f"[조문조회] 캐시 히트: {cache_key}")
            return self._law_cache[cache_key]

        # 조번호 추출 (제60조 → 60)
        jo_match = re.search(r'제(\d+)조', article_num)
        if not jo_match:
            print(f"[조문조회] 조번호 파싱 실패: {article_num}")
            return None

        jo = jo_match.group(1)
        jo_padded = jo.zfill(4)  # 60 → 0060

        # 조례 여부 판단 (조례, 규칙 등)
        is_ordinance = '조례' in law_name or '규칙' in law_name

        try:
            law_name_encoded = law_name.replace(' ', '')

            if is_ordinance:
                # 지방자치법규 (조례/규칙)
                article_url = f"https://www.law.go.kr/자치법규/{law_name_encoded}/{article_num}"
                res = self.session.get(article_url, timeout=20, allow_redirects=True)
                res.encoding = 'utf-8'

                # ordinSeq 추출
                seq_match = re.search(r'ordinSeq=(\d+)', res.text)
                if not seq_match:
                    print(f"[조문조회] {law_name} ordinSeq 추출 실패")
                    return None

                seq = seq_match.group(1)

                # 조례 상세 페이지 호출
                detail_url = "https://www.law.go.kr/LSW/ordinSideInfoP.do"
                params = {
                    "ordinSeq": seq,
                    "joNo": jo_padded,
                    "joBrNo": "00",
                    "docCls": "jo",
                    "urlMode": "ordinScJoAllRltInfoR"
                }
            else:
                # 국가법령 (법률, 시행령, 시행규칙)
                article_url = f"https://www.law.go.kr/법령/{law_name_encoded}/{article_num}"
                res = self.session.get(article_url, timeout=20, allow_redirects=True)
                res.encoding = 'utf-8'

                # lsiSeq 추출
                seq_match = re.search(r'lsiSeq=(\d+)', res.text)
                if not seq_match:
                    print(f"[조문조회] {law_name} lsiSeq 추출 실패")
                    return None

                seq = seq_match.group(1)

                # 법령 상세 페이지 호출
                detail_url = "https://www.law.go.kr/LSW/lsSideInfoP.do"
                params = {
                    "lsiSeq": seq,
                    "joNo": jo_padded,
                    "joBrNo": "00",
                    "docCls": "jo",
                    "urlMode": "lsScJoRltInfoR"
                }

            res = self.session.get(detail_url, params=params, timeout=20)
            res.encoding = 'utf-8'
            html = res.text

            # 조문 내용 파싱
            article_parts = []

            # 조문 제목 및 본문 (pty1_p4)
            title_match = re.search(r'<p class="pty1_p4"[^>]*>(.*?)</p>', html, re.DOTALL)
            if title_match:
                text = title_match.group(1)
                text = re.sub(r'<[^>]+>', '', text)
                text = re.sub(r'\s+', ' ', text).strip()
                article_parts.append(text)

            # 항/호 내용 (pty1_de2, pty1_de2_1, pty1_de3 등)
            for match in re.finditer(r'<p class="pty1_de[23][^"]*"[^>]*>(.*?)</p>', html, re.DOTALL):
                text = match.group(1)
                text = re.sub(r'<[^>]+>', '', text)
                text = re.sub(r'\s+', ' ', text).strip()
                # 삭제된 항, 개정이력 제외
                if text and not text.startswith('삭제') and not text.startswith('['):
                    article_parts.append(text)

            if article_parts:
                article_content = '\n'.join(article_parts)
                self._law_cache[cache_key] = article_content
                print(f"[조문조회] {law_name} {article_num} 조회 성공 ({len(article_content)}자)")
                return article_content
            else:
                print(f"[조문조회] {law_name} {article_num} 조문 내용 없음")
                return None

        except Exception as e:
            print(f"[조문조회] 오류: {e}")
            return None

    def get_law_articles_batch(self, laws: List[Dict]) -> List[Dict]:
        """
        여러 법령 조문을 일괄 조회 (law.go.kr 웹 스크래핑)

        Args:
            laws: [{"법령명": "건축법", "조항": "제60조", "내용": "..."}, ...]

        Returns:
            조문_전문 필드가 추가된 리스트
        """
        for law in laws:
            full_text = self.get_law_article_text(law['법령명'], law['조항'])
            law['조문_전문'] = full_text

        return laws

    def search_address(self, keyword: str) -> List[Dict]:
        """
        주소 검색 → 필지(PNU) 목록 반환

        Args:
            keyword: 검색할 주소 (예: "서울 강남구 강남대로 382")

        Returns:
            [{"pnu": "...", "address": "...", "jibun": "825-12"}, ...]
        """
        res = self.session.post(
            "https://www.eum.go.kr/web/am/mp/mpSearchAddrAjaxXml.jsp",
            data={"sId": "selectAdAddrList", "keyword": keyword},
            headers=self.headers
        )

        # JSON 응답에서 XML 추출
        try:
            data = json.loads(res.text)
            xml_content = data.get('roadBonBuList', '')
        except json.JSONDecodeError:
            xml_content = res.text

        # XML 파싱
        pnus = re.findall(r'<pnu>(\d+)</pnu>', xml_content)
        addresses = re.findall(r'<subFullStr>([^<]+)</subFullStr>', xml_content)
        jibuns = re.findall(r'<jujibun>(\d+)</jujibun>', xml_content)
        bujibuns = re.findall(r'<bujibun>(\d+)</bujibun>', xml_content)

        results = []
        for i, pnu in enumerate(pnus):
            results.append({
                "pnu": pnu,
                "address": addresses[i] if i < len(addresses) else "",
                "jibun": f"{jibuns[i]}-{bujibuns[i]}" if i < len(jibuns) and i < len(bujibuns) else ""
            })

        print(f"[검색] '{keyword}' → {len(results)}개 필지 발견")
        return results

    def get_land_price(self, pnu: str) -> Dict:
        """
        공시지가 조회

        Args:
            pnu: 19자리 필지고유번호

        Returns:
            {"공시지가": 85100000, "기준년도": "2025", "단위": "원/㎡"}
        """
        # PNU 파싱: 시군구(5) + 법정동(5) + 산(1) + 본번(4) + 부번(4)
        adm_sect_cd = pnu[:5]
        land_loc_cd = pnu[5:10]
        bobn = pnu[11:15]
        bubn = pnu[15:19]

        url_param = f"adm_sect_cd={adm_sect_cd}|land_loc_cd={land_loc_cd}|ledg_gbn=1|bobn={bobn}|bubn={bubn}"

        res = self.session.get(
            "https://api.eum.go.kr/web/api/korep/UrlConnector.jsp",
            params={"url": url_param},
            headers=self.headers
        )

        jiga = re.search(r'<JIGA>(\d+)</JIGA>', res.text)
        year = re.search(r'<BASE_YEAR>(\d+)</BASE_YEAR>', res.text)

        result = {
            "공시지가": int(jiga.group(1)) if jiga else None,
            "기준년도": year.group(1) if year else None,
            "단위": "원/㎡"
        }

        print(f"[공시지가] {result['공시지가']:,}원/㎡ ({result['기준년도']}년)" if result['공시지가'] else "[공시지가] 조회 실패")
        return result

    def get_land_use_plan(self, pnu: str, ucodes: str = None) -> Dict:
        """
        토지이용계획 상세 조회 (건폐율, 용적률, 용도지역 등)

        Args:
            pnu: 19자리 필지고유번호
            ucodes: 용도지역 코드 (기본값 사용)

        Returns:
            {"건폐율": "60%", "용적률": "200%", "용도지역": [...], ...}
        """
        if ucodes is None:
            ucodes = "UQA01X;UQA220;UQQ300;UQS113;UDX200;UNE200;UBA100;UMK600;U99999;UQQ600;ZA0013"

        sggcd = pnu[:5]  # 시군구 코드

        res = self.session.get(
            "https://www.eum.go.kr/web/ar/lu/luLandDetUseGYAjax.jsp",
            params={
                "ucodes": ucodes,
                "sggcd": sggcd,
                "pnu": pnu,
                "carGbn": "GY"
            },
            headers=self.headers
        )

        html = res.text

        # 건폐율/용적률 추출 (input hidden 필드에서)
        # <input id="gun_basic_UQA220" value="60"/>
        coverage = re.search(r'id="gun_basic_\w+" value="\s*(\d+)"', html)
        floor_ratio = re.search(r'id="yong_basic_\w+" value="\s*(\d+)"', html)

        # 서울도심 용적률 (추가)
        floor_ratio_sub = re.search(r'(\d+)%\s*<br/>\s*(\d+)%', html)

        # 용도지역/지구 추출
        zones = re.findall(r'>([^<]*(?:주거지역|상업지역|공업지역|녹지지역|관리지역|농림지역|자연환경보전지역|지구|구역))</(?:th|td)>', html)
        zones = list(set([z.strip() for z in zones if z.strip()]))

        # 규제 법령 기준일
        law_date = re.search(r'규제 법령 기준일 : (\d{4}\.\d{2}\.\d{2})', html)

        # 용적률 (기본 + 서울도심)
        floor_ratio_value = f"{floor_ratio.group(1)}%" if floor_ratio else "N/A"
        if floor_ratio_sub:
            floor_ratio_value = f"{floor_ratio_sub.group(1)}% / {floor_ratio_sub.group(2)}% (서울도심)"

        result = {
            "pnu": pnu,
            "건폐율": f"{coverage.group(1)}%" if coverage else "N/A",
            "용적률": floor_ratio_value,
            "용도지역_지구": zones,
            "규제법령_기준일": law_date.group(1) if law_date else None,
            "raw_html": html  # LLM 분석용 원본
        }

        print(f"[토지이용계획] 건폐율: {result['건폐율']}, 용적률: {result['용적률']}")
        print(f"[용도지역] {result['용도지역_지구']}")
        return result

    def get_activity_restrictions(self, pnu: str, ucodes: str = None, include_full_text: bool = False) -> Dict:
        """
        행위제한내용 조회 (건축 가능/불가 건축물 + 관련 법령)
        - luLandDetUseKDAjax.jsp (carGbn=K, K2)

        Args:
            pnu: 19자리 필지고유번호
            ucodes: 용도지역 코드 (기본값 사용)
            include_full_text: True면 법령 조문 전문도 조회

        Returns:
            {"용도지역별_행위제한": [...], "건축가능건축물": [...], "건축불가건축물": [...], ...}
        """
        if ucodes is None:
            ucodes = "UQA01X;UQA220;UQQ300;UQS113;UDX200;UNE200;UBA100;UMK600;U99999;UQQ600;ZA0013"

        sggcd = pnu[:5]

        # carGbn=K (행위제한내용 - 용도지역별)
        res_k = self.session.get(
            "https://www.eum.go.kr/web/ar/lu/luLandDetUseKDAjax.jsp",
            params={
                "ucodes": ucodes,
                "sggcd": sggcd,
                "pnu": pnu,
                "carGbn": "K"
            },
            headers=self.headers
        )
        # eum.go.kr은 euc-kr 인코딩 사용
        res_k.encoding = 'euc-kr'
        html_k = res_k.text

        # carGbn=K2 (행위제한내용 - 상세)
        res_k2 = self.session.get(
            "https://www.eum.go.kr/web/ar/lu/luLandDetUseKDAjax.jsp",
            params={
                "ucodes": ucodes,
                "sggcd": sggcd,
                "pnu": pnu,
                "carGbn": "K2"
            },
            headers=self.headers
        )
        res_k2.encoding = 'euc-kr'
        html_k2 = res_k2.text

        # HTML 파싱 - 용도지역별 행위제한
        combined_html = html_k + html_k2

        # 용도지역명 추출: <span class="font_red title">일반상업지역</span>
        zone_names = re.findall(r'<span[^>]*class="[^"]*font_red[^"]*title[^"]*"[^>]*>([^<]+)</span>', combined_html)
        zone_names = list(set([z.strip() for z in zone_names if z.strip()]))
        if not zone_names:
            # 대체 패턴
            zone_names = re.findall(r'>([^<]*(?:지역|지구|구역))</span>', combined_html)
            zone_names = list(set([z.strip() for z in zone_names if z.strip() and len(z.strip()) > 3]))

        # 관련 법령 추출: <strong>건축법</strong> 제3조 ... <span class="mblock">(적용 제외)</span>
        activity_laws = []

        # 패턴: <strong>법령명</strong> 제XX조 ... <span class="mblock">(내용)</span>
        # 중간에 <span class="blind">...</span></a> 등이 있을 수 있음
        law_pattern = re.findall(
            r'<strong[^>]*>([^<]+)</strong>\s*(제\d+조(?:의\d+)?).*?<span\s+class="mblock">\(([^)]+)\)</span>',
            combined_html,
            re.DOTALL
        )
        for law_name, article, content in law_pattern:
            law_name = law_name.strip()
            article = article.strip()
            content = content.strip()
            if law_name:
                activity_laws.append({
                    "법령명": law_name,
                    "조항": article,
                    "내용": content
                })

        # 추가 패턴: <strong>법령명</strong> 제XX조 (mblock 없는 경우)
        law_pattern2 = re.findall(
            r'<strong[^>]*>([^<]+)</strong>\s*(제\d+조(?:의\d+)?)',
            combined_html
        )
        for law_name, article in law_pattern2:
            law_name = law_name.strip()
            article = article.strip()
            if law_name and not any(l['법령명'] == law_name and l['조항'] == article for l in activity_laws):
                activity_laws.append({
                    "법령명": law_name,
                    "조항": article,
                    "내용": ""
                })

        # 중복 제거
        seen = set()
        unique_laws = []
        for law in activity_laws:
            key = (law['법령명'], law['조항'])
            if key not in seen:
                seen.add(key)
                unique_laws.append(law)
        activity_laws = unique_laws

        # 건축할 수 있는/없는 건축물 (이 엔드포인트에서는 주로 법령 정보만 있음)
        buildable = []
        non_buildable = []

        # 조문 전문 조회 (옵션)
        if include_full_text and activity_laws:
            activity_laws = self.get_law_articles_batch(activity_laws)

        result = {
            "pnu": pnu,
            "용도지역": zone_names,
            "건축가능건축물": buildable,
            "건축불가건축물": non_buildable,
            "행위제한_관련법령": activity_laws,
            "raw_html": {
                "K": html_k,
                "K2": html_k2
            }
        }

        print(f"[행위제한내용] 용도지역: {result['용도지역']}")
        print(f"[건축가능] {len(buildable)}개 항목")
        print(f"[건축불가] {len(non_buildable)}개 항목")
        print(f"[관련법령] {len(activity_laws)}개 법령 발견")
        for law in activity_laws[:5]:
            print(f"   - {law['법령명']} {law['조항']}")

        return result

    def get_zone_law_details(self, pnu: str, ucode: str = "UQA220", include_full_text: bool = False) -> Dict:
        """
        용도지역별 법령 상세 조회 (lwLawDetContentsAjax.jsp)
        - 행위제한, 건폐율, 용적률, 건축/도로조건 등

        Args:
            pnu: 19자리 필지고유번호
            ucode: 용도지역 코드 (예: UQA220=일반상업지역, UQA100=제1종일반주거지역)
            include_full_text: True면 법령 조문 전문도 조회

        Returns:
            {"행위제한": {...}, "건폐율": {...}, "용적률": {...}, "건축도로조건": {...}, ...}
        """
        sggcd = pnu[:5]  # AREA_CODE로 사용

        # carGbn=all로 전체 데이터 조회
        res = self.session.get(
            "https://www.eum.go.kr/web/ar/lw/lwLawDetContentsAjax.jsp",
            params={
                "AREA_CODE": sggcd,
                "ucode": ucode,
                "carGbn": "all"
            },
            headers=self.headers
        )
        # eum.go.kr은 EUC-KR 인코딩 사용
        res.encoding = 'euc-kr'
        html = res.text

        # 개별 carGbn 조회
        details = {}
        car_gbn_map = {
            "0": "행위제한",
            "1": "건폐율",
            "2": "용적률",
            "4": "건축도로조건"
        }

        for gbn, name in car_gbn_map.items():
            res_detail = self.session.get(
                "https://www.eum.go.kr/web/ar/lw/lwLawDetContentsAjax.jsp",
                params={
                    "AREA_CODE": sggcd,
                    "ucode": ucode,
                    "carGbn": gbn
                },
                headers=self.headers
            )
            res_detail.encoding = 'euc-kr'
            details[name] = res_detail.text

        # HTML 파싱 - 법령명과 조항 추출
        # 구조: <SPAN CLASS='SPAN_JO_TITLE'>건축법</SPAN>...<a>...</a>&nbsp;제3조</SPAN>
        laws = []

        # 패턴 1: <SPAN CLASS='SPAN_JO_TITLE'>법령명</SPAN> ... 제XX조
        law_article_pattern = re.findall(
            r"<SPAN\s+CLASS='SPAN_JO_TITLE'>([^<]+)</SPAN>.*?&nbsp;(제\d+조(?:의\d+)?)</SPAN>",
            html
        )

        for law_name, article in law_article_pattern:
            law_name = law_name.strip()
            article = article.strip()

            # 카테고리 추출: 제XX조(제목) 뒤에 오는 lconbtn 클래스에서
            # 예: <span class="lconbtn02">건축선(경계)</span><span class="lconbtn03">도로조건(요건)</span>
            categories = []
            category_pattern = rf'{re.escape(article)}\([^)]+\)\s*</[^>]+>(.*?)(?:<P\s|</SPAN\s*id)'
            category_match = re.search(category_pattern, html, re.DOTALL)
            if category_match:
                # lconbtn 클래스에서 카테고리 추출
                cat_btns = re.findall(r'class="lconbtn\d+"[^>]*>([^<]+)</span>', category_match.group(1))
                categories = [c.strip() for c in cat_btns if c.strip()]

            if not any(l['법령명'] == law_name and l['조항'] == article for l in laws):
                laws.append({
                    "법령명": law_name,
                    "조항": article,
                    "분류": ", ".join(categories) if categories else "",
                    "내용": ""
                })

        # 카테고리별 법령 분류
        categorized_laws = {
            "행위제한": [],
            "건폐율": [],
            "용적률": [],
            "건축선_도로조건": []
        }

        for law in laws:
            cat = law.get('분류', '')
            if '행위제한' in cat:
                categorized_laws["행위제한"].append(law)
            elif '건폐율' in cat:
                categorized_laws["건폐율"].append(law)
            elif '용적률' in cat:
                categorized_laws["용적률"].append(law)
            elif '건축선' in cat or '도로조건' in cat or '대지' in cat:
                categorized_laws["건축선_도로조건"].append(law)
            else:
                # 분류가 없으면 법령명으로 추정
                if '건폐율' in str(law):
                    categorized_laws["건폐율"].append(law)
                elif '용적률' in str(law):
                    categorized_laws["용적률"].append(law)
                else:
                    categorized_laws["행위제한"].append(law)

        # 건폐율/용적률 수치 추출 (서울시 조례 기준: "일반상업지역: XX퍼센트" 형식)
        # carGbn=1 (건폐율) 에서 추출
        coverage_html = details.get('건폐율', html)
        seoul_coverage = re.search(r'일반상업지역:\s*(\d+)\s*퍼센트', coverage_html)
        # 대안: 국토법 기준 ("일반상업지역 : 80퍼센트" 형식, 공백 있음)
        if not seoul_coverage:
            seoul_coverage = re.search(r'일반상업지역\s*:\s*(\d+)\s*퍼센트', coverage_html)

        # carGbn=2 (용적률) 에서 추출
        floor_ratio_html = details.get('용적률', html)
        seoul_floor_ratio = re.search(r'일반상업지역:\s*(\d+)\s*퍼센트', floor_ratio_html)
        if not seoul_floor_ratio:
            seoul_floor_ratio = re.search(r'일반상업지역\s*:\s*(\d+)\s*퍼센트', floor_ratio_html)

        # 건축할 수 없는 건축물 추출 (별표 9 등)
        cannot_build = []
        # 패턴: "가. 「건축법 시행령」 별표 1 제15호의 숙박시설..."
        cannot_build_section = re.search(r'건축할\s*수\s*없는\s*건축물(.*?)(?:2\.\s*지역|건축할\s*수\s*있는|$)', html, re.DOTALL)
        if cannot_build_section:
            # "가.", "나.", "다." 등으로 시작하는 항목
            items = re.findall(r'[가-자]\.\s*([^\n가-자]+)', cannot_build_section.group(1))
            cannot_build = [item.strip()[:100] for item in items if item.strip() and len(item.strip()) > 5]

        # 추가: 별표 9에서 직접 추출
        if not cannot_build:
            byulpyo_section = re.search(r'\[별표\s*9\](.*?)(?:\[별표|$)', html, re.DOTALL)
            if byulpyo_section:
                items = re.findall(r'[가-자]\.\s*「[^」]+」[^가-자\n]+', byulpyo_section.group(1))
                cannot_build = [item.strip()[:100] for item in items if item.strip()]

        # 조문 전문 조회 (옵션)
        if include_full_text and laws:
            laws = self.get_law_articles_batch(laws)

        result = {
            "pnu": pnu,
            "용도지역코드": ucode,
            "건폐율_기준": f"{seoul_coverage.group(1)}%" if seoul_coverage else "60%",
            "용적률_기준": f"{seoul_floor_ratio.group(1)}%" if seoul_floor_ratio else "800%",
            "건축불가건축물": cannot_build[:20],
            "법령_카테고리별": categorized_laws,
            "관련법령_전체": laws,
            "raw_html": {
                "all": html,
                **details
            }
        }

        print(f"[용도지역법령] ucode: {ucode}")
        print(f"[용도지역법령] 관련법령 {len(laws)}개 발견")
        print(f"[용도지역법령] 카테고리: 행위제한({len(categorized_laws['행위제한'])}), "
              f"건폐율({len(categorized_laws['건폐율'])}), "
              f"용적률({len(categorized_laws['용적률'])}), "
              f"건축선/도로({len(categorized_laws['건축선_도로조건'])})")
        for law in laws[:5]:
            print(f"   - {law['법령명']} {law['조항']} [{law.get('분류', '')}]")

        return result

    def get_restrictions(self, pnu: str, ucodes: str = None, include_full_text: bool = False) -> Dict:
        """
        행위제한 및 규제법령 조회

        Args:
            pnu: 19자리 필지고유번호
            ucodes: 용도지역 코드 (기본값 사용)
            include_full_text: True면 법령 조문 전문도 조회 (law_oc 필요)

        Returns:
            {"높이제한": {...}, "규제법령": [...], ...}
        """
        if ucodes is None:
            ucodes = "UQA01X;UQA220;UQQ300;UQS113;UDX200;UNE200;UBA100;UMK600;U99999;UQQ600;ZA0013"

        sggcd = pnu[:5]

        res = self.session.get(
            "https://www.eum.go.kr/web/ar/lu/luLandDetUseCAjax.jsp",
            params={
                "ucodes": ucodes,
                "markUcodes": "UQA01X;UQA220;UQQ300;UQS113",
                "sggcd": sggcd,
                "pnu": pnu,
                "carGbn": "C"
            },
            headers=self.headers
        )

        html = res.text

        # 높이제한 추출
        height_10m = re.search(r'10미터 이하<br>이격거리<br>(\d+)m', html)
        height_over_10m = re.search(r'10미터 초과<br>이격거리<br>부분높이 (\d+)', html)

        # 규제법령 추출
        laws = []
        law_patterns = re.findall(
            r'<strong[^>]*>([^<]+)</strong>\s*([^<]+)<span[^>]*>[^<]*</span>.*?<span class="mblock">\(([^)]+)\)</span>',
            html
        )
        for law_name, clause, desc in law_patterns:
            laws.append({
                "법령명": law_name.strip(),
                "조항": clause.strip(),
                "내용": desc.strip()
            })

        # 규제지역명 추출
        restriction_areas = re.findall(r'<span class="font_red title">([^<]+)</span>', html)

        # 조문 전문 조회 (옵션) - 웹 스크래핑 방식
        if include_full_text:
            laws = self.get_law_articles_batch(laws)

        result = {
            "pnu": pnu,
            "높이제한": {
                "일조권_10m이하_이격거리": f"{height_10m.group(1)}m" if height_10m else "N/A",
                "일조권_10m초과_부분높이": height_over_10m.group(1) if height_over_10m else "N/A",
            },
            "규제지역": restriction_areas,
            "규제법령": laws,
            "raw_html": html
        }

        print(f"[행위제한] 규제지역: {result['규제지역']}")
        print(f"[규제법령] {len(laws)}개 법령 발견")
        for law in laws[:3]:
            print(f"   - {law['법령명']} {law['조항']} ({law['내용']})")
            if include_full_text and law.get('조문_전문'):
                print(f"     전문: {law['조문_전문'][:100]}...")
        return result

    def get_full_land_info(self, pnu: str, include_full_text: bool = False) -> Dict:
        """
        전체 토지 정보 수집 (공시지가 + 토지이용계획 + 규제법령)

        Args:
            pnu: 19자리 필지고유번호
            include_full_text: True면 법령 조문 전문도 조회 (law_oc 필요)

        Returns:
            통합된 토지 정보 딕셔너리
        """
        print(f"\n{'='*50}")
        print(f"[수집 시작] PNU: {pnu}")
        if include_full_text:
            print(f"[옵션] 법령 조문 전문 조회: {'활성화' if self.law_oc else '비활성화(law_oc 미설정)'}")
        print('='*50)

        # 공시지가
        price_info = self.get_land_price(pnu)

        # 토지이용계획
        land_use_info = self.get_land_use_plan(pnu)

        # 행위제한 및 규제법령 (carGbn=C)
        restriction_info = self.get_restrictions(pnu, include_full_text=include_full_text)

        # 행위제한내용 (carGbn=K, K2) - 건축 가능/불가 건축물
        activity_info = self.get_activity_restrictions(pnu, include_full_text=include_full_text)

        # 용도지역 코드 추출 (용도지역별 법령 조회용)
        # 용도지역명 → ucode 매핑
        zone_to_ucode = {
            "제1종전용주거지역": "UQA110",
            "제2종전용주거지역": "UQA120",
            "제1종일반주거지역": "UQA130",
            "제2종일반주거지역": "UQA140",
            "제3종일반주거지역": "UQA150",
            "준주거지역": "UQA160",
            "중심상업지역": "UQA210",
            "일반상업지역": "UQA220",
            "근린상업지역": "UQA230",
            "유통상업지역": "UQA240",
            "전용공업지역": "UQA310",
            "일반공업지역": "UQA320",
            "준공업지역": "UQA330",
            "보전녹지지역": "UQA410",
            "생산녹지지역": "UQA420",
            "자연녹지지역": "UQA430",
        }

        # 첫 번째 용도지역의 ucode 찾기
        primary_ucode = "UQA220"  # 기본값: 일반상업지역
        for zone in land_use_info.get('용도지역_지구', []):
            for zone_name, ucode in zone_to_ucode.items():
                if zone_name in zone:
                    primary_ucode = ucode
                    break

        # 용도지역별 법령 상세 (lwLawDetContentsAjax.jsp)
        zone_law_info = self.get_zone_law_details(pnu, ucode=primary_ucode, include_full_text=include_full_text)

        # 통합
        result = {
            "pnu": pnu,
            "공시지가": price_info,
            "토지이용계획": {
                "건폐율": land_use_info['건폐율'],
                "용적률": land_use_info['용적률'],
                "용도지역_지구": land_use_info['용도지역_지구'],
                "규제법령_기준일": land_use_info['규제법령_기준일'],
            },
            "행위제한": {
                "높이제한": restriction_info['높이제한'],
                "규제지역": restriction_info['규제지역'],
                "규제법령": restriction_info['규제법령'],
            },
            "행위제한내용": {
                "용도지역": activity_info['용도지역'],
                "건축가능건축물": activity_info['건축가능건축물'],
                "건축불가건축물": activity_info['건축불가건축물'],
                "관련법령": activity_info['행위제한_관련법령'],
            },
            "용도지역별_법령상세": {
                "용도지역코드": zone_law_info['용도지역코드'],
                "건폐율_기준": zone_law_info['건폐율_기준'],
                "용적률_기준": zone_law_info['용적률_기준'],
                "건축불가건축물": zone_law_info['건축불가건축물'],
                "법령_카테고리별": zone_law_info['법령_카테고리별'],
                "관련법령_전체": zone_law_info['관련법령_전체'],
            },
            "raw_html": {
                "토지이용계획": land_use_info['raw_html'],
                "행위제한": restriction_info['raw_html'],
                "행위제한내용_K": activity_info['raw_html']['K'],
                "행위제한내용_K2": activity_info['raw_html']['K2'],
                "용도지역법령": zone_law_info['raw_html'],
            }
        }

        print(f"\n[수집 완료]")
        return result


def main():
    """테스트 실행"""
    collector = EumLandCollector()

    # 1. 주소 검색
    keyword = input("\n검색할 주소를 입력하세요: ").strip()
    if not keyword:
        keyword = "서울 강남구 강남대로 382"
        print(f"기본 주소 사용: {keyword}")

    print(f"\n주소 검색 중: {keyword}")
    results = collector.search_address(keyword)

    if not results:
        print("검색 결과 없음")
        return

    # 검색 결과 표시 (최대 10개)
    print("\n" + "="*50)
    print("검색 결과")
    print("="*50)
    display_count = min(len(results), 10)
    for i, r in enumerate(results[:display_count]):
        print(f"  {i+1}. {r['address']} {r['jibun']}")

    if len(results) > display_count:
        print(f"  ... 외 {len(results) - display_count}개")

    # 2. 사용자 선택
    print()
    while True:
        try:
            choice = input(f"선택할 번호를 입력하세요 (1-{display_count}): ").strip()
            choice_num = int(choice)
            if 1 <= choice_num <= display_count:
                break
            print(f"1에서 {display_count} 사이의 숫자를 입력하세요.")
        except ValueError:
            print("숫자를 입력하세요.")

    selected = results[choice_num - 1]
    print(f"\n선택됨: {selected['address']} {selected['jibun']}")

    # 3. 상세 조회 (조문 전문 포함)
    pnu = selected['pnu']
    land_info = collector.get_full_land_info(pnu, include_full_text=True)

    # 4. 결과 출력 (raw_html 제외, 주소 정보 추가)
    output = {
        "주소": selected['address'],
        "지번": selected['jibun'],
        **{k: v for k, v in land_info.items() if k != 'raw_html'}
    }

    # 4. JSON 파일로 저장
    output_filename = f"land_info_{pnu}.json"
    with open(output_filename, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # 디버깅용: raw HTML 저장
    if land_info.get('raw_html'):
        raw_html = land_info['raw_html']
        # 행위제한내용 K, K2 HTML 저장
        if raw_html.get('행위제한내용_K'):
            with open(f"debug_K_{pnu}.html", 'w', encoding='utf-8') as f:
                f.write(raw_html['행위제한내용_K'])
            print(f"[디버그] debug_K_{pnu}.html 저장됨")
        if raw_html.get('행위제한내용_K2'):
            with open(f"debug_K2_{pnu}.html", 'w', encoding='utf-8') as f:
                f.write(raw_html['행위제한내용_K2'])
            print(f"[디버그] debug_K2_{pnu}.html 저장됨")
        # 용도지역 법령 HTML 저장
        if raw_html.get('용도지역법령') and raw_html['용도지역법령'].get('all'):
            with open(f"debug_zone_law_{pnu}.html", 'w', encoding='utf-8') as f:
                f.write(raw_html['용도지역법령']['all'])
            print(f"[디버그] debug_zone_law_{pnu}.html 저장됨")

    print("\n" + "="*50)
    print(f"결과 저장 완료: {output_filename}")
    print("="*50)

    # 5. 조문 전문 샘플 출력
    print("\n규제법령 조문 전문 샘플:")
    for law in land_info['행위제한']['규제법령'][:3]:
        print(f"\n  {law['법령명']} {law['조항']} ({law['내용']})")
        if law.get('조문_전문'):
            print(f"  전문: {law['조문_전문'][:200]}...")

    # 6. 행위제한내용 출력
    print("\n" + "="*50)
    print("행위제한내용 (건축 가능/불가 건축물)")
    print("="*50)
    if land_info.get('행위제한내용'):
        act = land_info['행위제한내용']
        print(f"\n용도지역: {act.get('용도지역', [])}")
        print(f"\n건축 가능한 건축물 ({len(act.get('건축가능건축물', []))}개):")
        for item in act.get('건축가능건축물', [])[:10]:
            print(f"  - {item}")
        if len(act.get('건축가능건축물', [])) > 10:
            print(f"  ... 외 {len(act['건축가능건축물']) - 10}개")

        print(f"\n건축 불가한 건축물 ({len(act.get('건축불가건축물', []))}개):")
        for item in act.get('건축불가건축물', [])[:10]:
            print(f"  - {item}")
        if len(act.get('건축불가건축물', [])) > 10:
            print(f"  ... 외 {len(act['건축불가건축물']) - 10}개")

        print(f"\n관련 법령 ({len(act.get('관련법령', []))}개):")
        for law in act.get('관련법령', [])[:5]:
            print(f"  - {law['법령명']} {law['조항']}")
            if law.get('조문_전문'):
                print(f"    전문: {law['조문_전문'][:150]}...")

    # 7. 용도지역별 법령 상세 출력
    print("\n" + "="*50)
    print("용도지역별 법령 상세 (lwLawDetContentsAjax)")
    print("="*50)
    if land_info.get('용도지역별_법령상세'):
        zone = land_info['용도지역별_법령상세']
        print(f"\n용도지역코드: {zone.get('용도지역코드', 'N/A')}")
        print(f"건폐율 기준: {zone.get('건폐율_기준', 'N/A')}")
        print(f"용적률 기준: {zone.get('용적률_기준', 'N/A')}")

        print(f"\n건축할 수 없는 건축물 ({len(zone.get('건축불가건축물', []))}개):")
        for item in zone.get('건축불가건축물', [])[:10]:
            print(f"  - {item}")

        print(f"\n법령 카테고리별:")
        cats = zone.get('법령_카테고리별', {})
        for cat_name, cat_laws in cats.items():
            print(f"  [{cat_name}] {len(cat_laws)}개")
            for law in cat_laws[:3]:
                print(f"    - {law['법령명']} {law['조항']}")

        print(f"\n관련 법령 전체 ({len(zone.get('관련법령_전체', []))}개):")
        for law in zone.get('관련법령_전체', [])[:5]:
            print(f"  - {law['법령명']} {law['조항']} [{law.get('분류', '')}]")


if __name__ == "__main__":
    main()
