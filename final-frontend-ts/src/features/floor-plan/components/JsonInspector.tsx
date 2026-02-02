// ============================================
// JsonInspector Component
// 카테고리별 노드 UI + 호버 툴팁 (그룹화)
// ============================================

import React, { useState } from 'react';
import { FiChevronDown, FiChevronRight, FiBox, FiHome, FiSquare } from 'react-icons/fi';
import type { HoverableItem, RoomInfo, StructureInfo, ObjectInfo, FloorPlanUploadResponse, GroupedHoverableItem } from '../types/floor-plan.types';
import { parseBbox, parseSegmentation } from '../types/floor-plan.types';
import styles from './JsonInspector.module.css';

interface JsonInspectorProps {
  data: FloorPlanUploadResponse | null;
  onHover: (items: HoverableItem[] | null) => void;
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

// 그룹화된 노드 아이템 컴포넌트
interface GroupedNodeItemProps {
  group: GroupedHoverableItem;
  isHovered: boolean;
  onHover: (items: HoverableItem[] | null) => void;
  color: string;
}

const GroupedNodeItem: React.FC<GroupedNodeItemProps> = ({ group, isHovered, onHover, color }) => {
  return (
    <div className={styles.nodeWrapper}>
      <div
        className={`${styles.node} ${isHovered ? styles.nodeHovered : ''}`}
        style={{
          borderColor: isHovered ? color : '#E5E7EB',
          backgroundColor: isHovered ? `${color}15` : '#FFFFFF'
        }}
        onMouseEnter={() => onHover(group.items)}
        onMouseLeave={() => onHover(null)}
      >
        <span className={styles.nodeName}>{group.name}</span>
        {group.count > 1 && (
          <span className={styles.nodeCount} style={{ backgroundColor: color }}>
            {group.count}
          </span>
        )}
      </div>
      {/* 호버 툴팁 */}
      {isHovered && group.totalAreaPercent !== undefined && (
        <div className={styles.tooltip}>
          <span className={styles.tooltipLabel}>비율</span>
          <span className={styles.tooltipValue}>{group.totalAreaPercent.toFixed(2)}%</span>
        </div>
      )}
    </div>
  );
};

// 아이템을 이름별로 그룹화
const groupByName = (items: HoverableItem[]): GroupedHoverableItem[] => {
  const groups = new Map<string, HoverableItem[]>();

  items.forEach(item => {
    const existing = groups.get(item.name) || [];
    existing.push(item);
    groups.set(item.name, existing);
  });

  return Array.from(groups.entries()).map(([name, groupItems]) => ({
    name,
    type: groupItems[0].type,
    count: groupItems.length,
    items: groupItems,
    totalAreaPercent: groupItems[0].areapercent !== undefined
      ? groupItems.reduce((sum, item) => sum + (item.areapercent || 0), 0)
      : undefined,
  }));
};

const JsonInspector: React.FC<JsonInspectorProps> = ({ data, onHover, hoveredItem }) => {
  // 현재 hover된 그룹 이름 추적
  const [hoveredGroupName, setHoveredGroupName] = useState<string | null>(null);
  const [hoveredGroupType, setHoveredGroupType] = useState<string | null>(null);

  if (!data) {
    return (
      <div className={styles.container}>
        <div className={styles.placeholder}>
          분석 결과가 없습니다
        </div>
      </div>
    );
  }

  // RoomInfo → HoverableItem 변환 (segmentation 포함)
  const roomItems: HoverableItem[] = data.rooms.map((room: RoomInfo) => ({
    id: room.id,
    type: 'room' as const,
    name: room.spcname || room.ocrname,
    bbox: parseBbox(room.bbox),
    areapercent: room.areapercent,
    segmentation: room.segmentation ? parseSegmentation(room.segmentation) || undefined : undefined,
  }));

  // StructureInfo → HoverableItem 변환 (segmentation 포함)
  const structureItems: HoverableItem[] = (data.structures || []).map((str: StructureInfo) => ({
    id: str.id,
    type: 'structure' as const,
    name: str.name,
    bbox: parseBbox(str.bbox),
    segmentation: str.segmentation ? parseSegmentation(str.segmentation) || undefined : undefined,
  }));

  // ObjectInfo → HoverableItem 변환 (YOLO라서 bbox만 있음)
  const objectItems: HoverableItem[] = (data.objects || []).map((obj: ObjectInfo) => ({
    id: obj.id,
    type: 'object' as const,
    name: obj.name,
    bbox: parseBbox(obj.bbox),
  }));

  // 그룹화
  const roomGroups = groupByName(roomItems);
  const structureGroups = groupByName(structureItems);
  const objectGroups = groupByName(objectItems);

  const handleGroupHover = (items: HoverableItem[] | null) => {
    if (items && items.length > 0) {
      setHoveredGroupName(items[0].name);
      setHoveredGroupType(items[0].type);
    } else {
      setHoveredGroupName(null);
      setHoveredGroupType(null);
    }
    onHover(items);
  };

  const isGroupHovered = (group: GroupedHoverableItem) =>
    hoveredGroupName === group.name && hoveredGroupType === group.type;

  return (
    <div className={styles.container}>
      {/* 요약 정보 */}
      <div className={styles.summary}>
        <div className={styles.summaryItem}>
          <span className={styles.summaryLabel}>공간 수</span>
          <span className={styles.summaryValue}>{data.roomCount}개</span>
        </div>
        <div className={styles.summaryItem}>
          <span className={styles.summaryLabel}>구조물</span>
          <span className={styles.summaryValue}>{structureItems.length}개</span>
        </div>
        <div className={styles.summaryItem}>
          <span className={styles.summaryLabel}>가구</span>
          <span className={styles.summaryValue}>{objectItems.length}개</span>
        </div>
      </div>

      {/* Rooms 섹션 */}
      <Section
        title="공간"
        icon={<FiHome size={14} />}
        count={roomItems.length}
        color="#3B82F6"
      >
        <div className={styles.nodeGrid}>
          {roomGroups.map((group) => (
            <GroupedNodeItem
              key={`room-group-${group.name}`}
              group={group}
              isHovered={isGroupHovered(group)}
              onHover={handleGroupHover}
              color="#3B82F6"
            />
          ))}
        </div>
      </Section>

      {/* Structures 섹션 */}
      {structureItems.length > 0 && (
        <Section
          title="구조물"
          icon={<FiSquare size={14} />}
          count={structureItems.length}
          color="#F97316"
          defaultExpanded={false}
        >
          <div className={styles.nodeGrid}>
            {structureGroups.map((group) => (
              <GroupedNodeItem
                key={`structure-group-${group.name}`}
                group={group}
                isHovered={isGroupHovered(group)}
                onHover={handleGroupHover}
                color="#F97316"
              />
            ))}
          </div>
        </Section>
      )}

      {/* Objects 섹션 */}
      {objectItems.length > 0 && (
        <Section
          title="가구"
          icon={<FiBox size={14} />}
          count={objectItems.length}
          color="#22C55E"
          defaultExpanded={false}
        >
          <div className={styles.nodeGrid}>
            {objectGroups.map((group) => (
              <GroupedNodeItem
                key={`object-group-${group.name}`}
                group={group}
                isHovered={isGroupHovered(group)}
                onHover={handleGroupHover}
                color="#22C55E"
              />
            ))}
          </div>
        </Section>
      )}
    </div>
  );
};

export default JsonInspector;
