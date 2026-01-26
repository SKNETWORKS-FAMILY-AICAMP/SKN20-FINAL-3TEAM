// ============================================
// JsonInspector Component
// 객체별 Hover 가능한 JSON 뷰어
// ============================================

import React, { useState } from 'react';
import { FiChevronDown, FiChevronRight, FiBox, FiHome, FiSquare } from 'react-icons/fi';
import type { HoverableItem, RoomInfo, StructureInfo, ObjectInfo, FloorPlanUploadResponse } from '../types';
import { parseBbox } from '../types';
import styles from './JsonInspector.module.css';

interface JsonInspectorProps {
  data: FloorPlanUploadResponse | null;
  onHover: (item: HoverableItem | null) => void;
  hoveredItem: HoverableItem | null;
}

// 섹션 컴포넌트
interface SectionProps {
  title: string;
  icon: React.ReactNode;
  count: number;
  color: string;
  children: React.ReactNode;
  defaultExpanded?: boolean;
}

const Section: React.FC<SectionProps> = ({
  title,
  icon,
  count,
  color,
  children,
  defaultExpanded = true,
}) => {
  const [expanded, setExpanded] = useState(defaultExpanded);

  return (
    <div className={styles.section}>
      <div
        className={styles.sectionHeader}
        onClick={() => setExpanded(!expanded)}
        style={{ borderLeftColor: color }}
      >
        <span className={styles.expandIcon}>
          {expanded ? <FiChevronDown size={14} /> : <FiChevronRight size={14} />}
        </span>
        <span className={styles.sectionIcon} style={{ color }}>
          {icon}
        </span>
        <span className={styles.sectionTitle}>{title}</span>
        <span className={styles.sectionCount} style={{ backgroundColor: color }}>
          {count}
        </span>
      </div>
      {expanded && <div className={styles.sectionContent}>{children}</div>}
    </div>
  );
};

// 아이템 Row 컴포넌트
interface ItemRowProps {
  item: HoverableItem;
  isHovered: boolean;
  onHover: (item: HoverableItem | null) => void;
  color: string;
}

const ItemRow: React.FC<ItemRowProps> = ({ item, isHovered, onHover, color }) => {
  return (
    <div
      className={`${styles.itemRow} ${isHovered ? styles.itemHovered : ''}`}
      style={{ borderLeftColor: isHovered ? color : 'transparent' }}
      onMouseEnter={() => onHover(item)}
      onMouseLeave={() => onHover(null)}
    >
      <div className={styles.itemMain}>
        <span className={styles.itemId}>#{item.id}</span>
        <span className={styles.itemName}>{item.name}</span>
      </div>
      <div className={styles.itemBbox}>
        [{item.bbox.join(', ')}]
      </div>
    </div>
  );
};

const JsonInspector: React.FC<JsonInspectorProps> = ({ data, onHover, hoveredItem }) => {
  if (!data) {
    return (
      <div className={styles.container}>
        <div className={styles.placeholder}>
          분석 결과가 없습니다
        </div>
      </div>
    );
  }

  // RoomInfo → HoverableItem 변환 (bbox 문자열 파싱)
  const roomItems: HoverableItem[] = data.rooms.map((room: RoomInfo) => ({
    id: room.id,
    type: 'room' as const,
    name: room.spcname || room.ocrname,
    bbox: parseBbox(room.bbox),
  }));

  // StructureInfo → HoverableItem 변환 (bbox 문자열 파싱)
  const structureItems: HoverableItem[] = (data.structures || []).map((str: StructureInfo) => ({
    id: str.id,
    type: 'structure' as const,
    name: str.name,
    bbox: parseBbox(str.bbox),
  }));

  // ObjectInfo → HoverableItem 변환 (bbox 문자열 파싱)
  const objectItems: HoverableItem[] = (data.objects || []).map((obj: ObjectInfo) => ({
    id: obj.id,
    type: 'object' as const,
    name: obj.name,
    bbox: parseBbox(obj.bbox),
  }));

  const isItemHovered = (item: HoverableItem) =>
    hoveredItem?.id === item.id && hoveredItem?.type === item.type;

  return (
    <div className={styles.container}>
      {/* 요약 정보 */}
      <div className={styles.summary}>
        <div className={styles.summaryItem}>
          <span className={styles.summaryLabel}>총 면적</span>
          <span className={styles.summaryValue}>{data.totalArea}㎡</span>
        </div>
        <div className={styles.summaryItem}>
          <span className={styles.summaryLabel}>공간 수</span>
          <span className={styles.summaryValue}>{data.roomCount}개</span>
        </div>
      </div>

      {/* Rooms 섹션 */}
      <Section
        title="Rooms"
        icon={<FiHome size={14} />}
        count={roomItems.length}
        color="#3B82F6"
      >
        {roomItems.map((item) => (
          <ItemRow
            key={`room-${item.id}`}
            item={item}
            isHovered={isItemHovered(item)}
            onHover={onHover}
            color="#3B82F6"
          />
        ))}
      </Section>

      {/* Structures 섹션 */}
      {structureItems.length > 0 && (
        <Section
          title="Structures"
          icon={<FiSquare size={14} />}
          count={structureItems.length}
          color="#F97316"
          defaultExpanded={false}
        >
          {structureItems.map((item) => (
            <ItemRow
              key={`structure-${item.id}`}
              item={item}
              isHovered={isItemHovered(item)}
              onHover={onHover}
              color="#F97316"
            />
          ))}
        </Section>
      )}

      {/* Objects 섹션 */}
      {objectItems.length > 0 && (
        <Section
          title="Objects"
          icon={<FiBox size={14} />}
          count={objectItems.length}
          color="#22C55E"
          defaultExpanded={false}
        >
          {objectItems.map((item) => (
            <ItemRow
              key={`object-${item.id}`}
              item={item}
              isHovered={isItemHovered(item)}
              onHover={onHover}
              color="#22C55E"
            />
          ))}
        </Section>
      )}
    </div>
  );
};

export default JsonInspector;
