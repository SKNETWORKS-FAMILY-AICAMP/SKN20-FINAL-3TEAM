// ============================================
// Chat Feature - Mock Data
// ============================================

import type { ChatSession, ChatMessage } from '../types';

// Mock 채팅 메시지
const mockMessages: ChatMessage[] = [
  {
    id: '1',
    role: 'user',
    content: '안녕 hello, 3Bay',
    timestamp: new Date('2024-01-19T10:00:00'),
  },
  {
    id: '2',
    role: 'assistant',
    content: `Artificial Intelligence (AI) offers numerous advantages and has the potential to revolutionize various aspects of our lives. Here are some key advantages of AI:

1. Automation: AI can automate repetitive and mundane tasks, saving time and effort for humans. It can handle large volumes of data, perform complex calculations, and execute tasks with precision and consistency. This automation leads to increased productivity and efficiency in various industries.

2. Decision-making: AI systems can analyze vast amounts of data, identify patterns, and make informed decisions based on that analysis. This ability is particularly useful in complex scenarios where humans may struggle to process large datasets or where quick and accurate decisions are crucial.

3. Improved accuracy: AI algorithms can achieve high levels of accuracy and precision in tasks such as image recognition, natural language processing, and data analysis. They can eliminate human errors caused by fatigue, distractions, or bias, leading to more reliable and consistent results.

4. Continuous operation: AI systems can work tirelessly without the need for breaks, resulting in uninterrupted 24/7 operations. This capability is especially beneficial in applications like customer support chatbots, manufacturing processes, and surveillance systems.`,
    timestamp: new Date('2024-01-19T10:01:00'),
  },
  {
    id: '3',
    role: 'user',
    content: '판상형 구조, 3Bay',
    timestamp: new Date('2024-01-19T10:05:00'),
  },
];

// Mock 채팅 세션
export const mockChatSessions: ChatSession[] = [
  {
    id: '1',
    title: 'adjfaweuhfodksdfkladsfajdshfw',
    messages: mockMessages,
    createdAt: new Date('2024-01-19T10:00:00'),
  },
  {
    id: '2',
    title: 'dafiefowihelwjenkwdfs',
    messages: [],
    createdAt: new Date('2024-01-18T15:30:00'),
  },
  {
    id: '3',
    title: 'kjaeifwhelsndlkfsjddafliwefwli',
    messages: [],
    createdAt: new Date('2024-01-17T09:20:00'),
  },
];
