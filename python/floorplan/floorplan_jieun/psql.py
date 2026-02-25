import psycopg2
from psycopg2.extras import RealDictCursor

def process_drawing_search(llm_output):
    """
    llm_output: LLM이 추출한 JSON 객체
    예: {"bay_cnt": "3,4", "k_op": "이상", "k_val": 0.2, "keyword": "주방,안방"}
    """
    # 모든 미지정 파라미터의 기본값을 문자열 'NULL'로 설정
    params = {
        "vent_grade": llm_output.get("vent_grade", "NULL"),
        "light_grade": llm_output.get("light_grade", "NULL"),
        "storage_grade": llm_output.get("storage_grade", "NULL"),
        "bay_cnt": llm_output.get("bay_cnt", "NULL"),
        "comp_grade": llm_output.get("comp_grade", "NULL"),
        "struc_type": llm_output.get("struc_type", "NULL"),
        
        # 비율 연산자 및 값 처리 (값이 없으면 SQL에서 무시됨)
        "k_op": llm_output.get("k_op", "NULL"),
        "k_val": str(llm_output.get("k_val", "NULL")),
        "lr_op": llm_output.get("lr_op", "NULL"),
        "lr_val": str(llm_output.get("lr_val", "NULL")),
        "wl_op": llm_output.get("wl_op", "NULL"),
        "wl_val": str(llm_output.get("wl_val", "NULL")),
        "val_op": llm_output.get("val_op", "NULL"),
        "val_val": str(llm_output.get("val_val", "NULL")),
        "to_op": llm_output.get("to_op", "NULL"),
        "to_val": str(llm_output.get("to_val", "NULL")),
        
        "keyword": llm_output.get("keyword", "NULL")
    }

    # 2. SQL 쿼리 (제시해주신 쿼리)
    query = """
SELECT
document_id
FROM "FP-Analysis"
WHERE 1=1

-- 환기 등급
AND (derived_vent_grade = :'vent_grade' OR :'vent_grade' = 'NULL')
AND (
    :'vent_grade' = 'NULL' OR
    document ~ ('ventilation은\(는\)\s*' || :'vent_grade')
)

-- 채광 등급
AND (derived_light_grade = :'light_grade' OR :'light_grade' = 'NULL')
AND (
    :'light_grade' = 'NULL' OR
    CASE
        WHEN :'light_grade' = '적합' THEN document ~ 'lighting은\(는\)\s*(우수|적합)'
        WHEN :'light_grade' = '보통' THEN document ~ 'lighting은\(는\)\s*보통'
        WHEN :'light_grade' = '부족' THEN document ~ 'lighting은\(는\)\s*(부족|미흡)'
        WHEN :'light_grade' = '부적합' THEN document ~ 'lighting은\(는\)\s*(부적합|불합격)'
        ELSE document ~ ('lighting은\(는\)\s*' || :'light_grade')
    END
)

-- 수납공간 등급
AND (
    :'storage_grade' = 'NULL' OR
    CASE
        WHEN :'storage_grade' = '적합' THEN document ~ 'storage은\(는\)\s*(우수|적합)'
        WHEN :'storage_grade' = '보통' THEN document ~ 'storage은\(는\)\s*보통'
        WHEN :'storage_grade' = '부족' THEN document ~ 'storage은\(는\)\s*(부족|미흡)'
        WHEN :'storage_grade' = '부적합' THEN document ~ 'storage은\(는\)\s*(부적합|불합격)'
        ELSE document ~ ('storage은\(는\)\s*' || :'storage_grade')
    END
)

-- A. 기본 구조 필터
AND (:'bay_cnt' = 'NULL' OR bay_count::text IN (SELECT unnest(string_to_array(:'bay_cnt', ','))))
AND (:'comp_grade' = 'NULL' OR compliance_grade = :'comp_grade')
AND (:'struc_type' = 'NULL' OR structure_type IN (SELECT unnest(string_to_array(:'struc_type', ','))))

-- B. 주방 비율 (5종 연산자)
AND (
%(k_val)s = 'NULL' OR %(k_op)s = 'NULL' OR
CASE :'k_op'
WHEN '이상' THEN kitchen_ratio::float >= :'k_val'::float
WHEN '이하' THEN kitchen_ratio::float <= :'k_val'::float
WHEN '초과' THEN kitchen_ratio::float > :'k_val'::float
WHEN '미만' THEN kitchen_ratio::float < :'k_val'::float
WHEN '동일' THEN kitchen_ratio::float = :'k_val'::float
ELSE TRUE
END
)

-- C. 거실 비율 (5종 연산자)
AND (
%(lr_op)s = 'NULL' OR %(lr_op)s = 'NULL' OR
CASE :'lr_op'
WHEN '이상' THEN living_room_ratio::float >= :'lr_val'::float
WHEN '이하' THEN living_room_ratio::float <= :'lr_val'::float
WHEN '초과' THEN living_room_ratio::float > :'lr_val'::float
WHEN '미만' THEN living_room_ratio::float < :'lr_val'::float
WHEN '동일' THEN living_room_ratio::float = :'lr_val'::float
ELSE TRUE
END
)

-- D. 무창 공간 비율 (5종 연산자)
AND (
%(wl_op)s = 'NULL' OR %(wl_op)s = 'NULL' OR
CASE :'wl_op'
WHEN '이상' THEN windowless_ratio::float >= :'wl_val'::float
WHEN '이하' THEN windowless_ratio::float <= :'wl_val'::float
WHEN '초과' THEN windowless_ratio::float > :'wl_val'::float
WHEN '미만' THEN windowless_ratio::float < :'wl_val'::float
WHEN '동일' THEN windowless_ratio::float = :'wl_val'::float
ELSE TRUE
END
)

-- 발코니 공간 비율 (5종 연산자)
AND (
%(val_op)s = 'NULL' OR %(val_op)s = 'NULL' OR
CASE :'val_op'
WHEN '이상' THEN windowless_ratio::float >= :'val_val'::float
WHEN '이하' THEN windowless_ratio::float <= :'val_val'::float
WHEN '초과' THEN windowless_ratio::float > :'val_val'::float
WHEN '미만' THEN windowless_ratio::float < :'val_val'::float
WHEN '동일' THEN windowless_ratio::float = :'val_val'::float
ELSE TRUE
END
)


-- 화장실 공간 비율 (5종 연산자)
AND (
%(to_op)s = 'NULL' OR %(to_op)s = 'NULL' OR
CASE :'to_op'
WHEN '이상' THEN windowless_ratio::float >= :'to_val'::float
WHEN '이하' THEN windowless_ratio::float <= :'to_val'::float
WHEN '초과' THEN windowless_ratio::float > :'to_val'::float
WHEN '미만' THEN windowless_ratio::float < :'to_val'::float
WHEN '동일' THEN windowless_ratio::float = :'to_val'::float
ELSE TRUE
END
)

-- E. 공간 명칭 키워드 및 상태 패턴
AND (
:'keyword' = 'NULL' OR
document ~* ALL(
SELECT TRIM(k)
FROM unnest(string_to_array(:'keyword', ',')) k
)
);
    """

    # 3. DB 실행
    try:
        conn = psycopg2.connect(dsn="your_connection_string")
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(query, params)
        results = cur.fetchall()
        cur.close()
        conn.close()
        return results
    except Exception as e:
        print(f"Error executing query: {e}")
        return []