// ============================================
// SettingsPage - Admin Settings
// ============================================

import { AdminLayout } from '../components/AdminLayout';
import styles from './AdminPages.module.css';

export function SettingsPage() {
  return (
    <AdminLayout>
      <div className={styles.page}>
        <h2 className={styles.pageTitle}>설정</h2>

        <div className={styles.settingsGrid}>
          {/* 일반 설정 */}
          <div className={styles.settingsCard}>
            <h3 className={styles.settingsTitle}>🔧 일반 설정</h3>
            <div className={styles.settingItem}>
              <label>관리자 이메일</label>
              <input type="email" defaultValue="admin@example.com" className={styles.settingInput} />
            </div>
            <div className={styles.settingItem}>
              <label>세션 타임아웃 (분)</label>
              <input type="number" defaultValue="30" className={styles.settingInput} />
            </div>
          </div>

          {/* 분석 설정 */}
          <div className={styles.settingsCard}>
            <h3 className={styles.settingsTitle}>🤖 AI 분석 설정</h3>
            <div className={styles.settingItem}>
              <label>최대 파일 크기 (MB)</label>
              <input type="number" defaultValue="50" className={styles.settingInput} />
            </div>
            <div className={styles.settingItem}>
              <label>지원 파일 형식</label>
              <input type="text" defaultValue="PDF, PNG, JPG" className={styles.settingInput} />
            </div>
            <div className={styles.settingItem}>
              <label>동시 분석 수</label>
              <input type="number" defaultValue="5" className={styles.settingInput} />
            </div>
          </div>

          {/* 알림 설정 */}
          <div className={styles.settingsCard}>
            <h3 className={styles.settingsTitle}>🔔 알림 설정</h3>
            <div className={styles.settingToggle}>
              <label>신규 가입 알림</label>
              <input type="checkbox" defaultChecked />
            </div>
            <div className={styles.settingToggle}>
              <label>분석 오류 알림</label>
              <input type="checkbox" defaultChecked />
            </div>
            <div className={styles.settingToggle}>
              <label>시스템 경고 알림</label>
              <input type="checkbox" defaultChecked />
            </div>
            <div className={styles.settingToggle}>
              <label>일일 리포트 발송</label>
              <input type="checkbox" />
            </div>
          </div>

          {/* 보안 설정 */}
          <div className={styles.settingsCard}>
            <h3 className={styles.settingsTitle}>🔒 보안 설정</h3>
            <div className={styles.settingToggle}>
              <label>2단계 인증 필수</label>
              <input type="checkbox" />
            </div>
            <div className={styles.settingItem}>
              <label>비밀번호 최소 길이</label>
              <input type="number" defaultValue="8" className={styles.settingInput} />
            </div>
            <div className={styles.settingItem}>
              <label>로그인 시도 제한</label>
              <input type="number" defaultValue="5" className={styles.settingInput} />
            </div>
          </div>
        </div>

        {/* 저장 버튼 */}
        <div className={styles.settingsFooter}>
          <button className={styles.secondaryBtn}>초기화</button>
          <button className={styles.primaryBtn}>변경사항 저장</button>
        </div>
      </div>
    </AdminLayout>
  );
}
