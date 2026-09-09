// Single place that maps a character's folder under `character reference/`
// to its URL slug, accent colour, and English display name.
// Accent colours are sampled from each character's poster scene (DESIGN.md: 每角色一个强调色取自其立绘场景).
// `hoverCell` picks which cell of the 3×3 expression sheet the card shows on hover:
//   0 neutral · 1 happy · 2 sad · 3 angry · 4 surprised · 5 shy · 6 sleepy · 7 smug · 8 crying

export const characters = [
  { slug: 'fufu',     folder: 'FUFU-enfp',    accent: '#E0782A', hoverCell: 1, en: { name: 'FUFU' } },
  { slug: 'haide',    folder: 'haide-entp',   accent: '#4C5D7C', hoverCell: 7, en: { name: 'Haide' } },
  { slug: 'mimi',     folder: 'Mimi-enfj',    accent: '#6A3D9E', hoverCell: 7, en: { name: 'Mimi' } },
  { slug: 'aisha',    folder: '艾莎-intj',     accent: '#8B1E33', hoverCell: 7, en: { name: 'Aisha' } },
  { slug: 'ruanruan', folder: '软软-infp',     accent: '#D98A94', hoverCell: 8, en: { name: 'Ruanruan' } },
  { slug: 'lukos',    folder: 'lukos-infj',   accent: '#6F849A', hoverCell: 5, en: { name: 'Lukos' } },
  { slug: 'whiskle',  folder: 'whiskle-infp', accent: '#6C8A5B', hoverCell: 5, en: { name: 'Whiskle' } },
  { slug: 'mushi',    folder: '牧师-enfj',     accent: '#D39A34', hoverCell: 1, en: { name: 'Mushi' } },
  { slug: 'dianer',   folder: '点儿-intp',     accent: '#6E7B8B', hoverCell: 6, en: { name: 'Dianer' } },
  { slug: 'luyao',    folder: '陆姚-entj',     accent: '#2E2B33', hoverCell: 3, en: { name: 'Luyao' } },
  { slug: 'liiie',    folder: 'Liiie-infj',   accent: '#B5306A', hoverCell: 6, en: { name: 'Liiie' } },
  { slug: 'qc',       folder: 'QC-entp',      accent: '#2C4A88', hoverCell: 7, en: { name: 'QC' } },
];

// Names as they appear inside bibles / story `cast` lists → slug
export const nameToSlug = Object.fromEntries(
  characters.flatMap((c) => {
    const zh = c.folder.split('-')[0];
    return [
      [zh, c.slug],
      [zh.toLowerCase(), c.slug],
      [c.en.name, c.slug],
      [c.en.name.toLowerCase(), c.slug],
    ];
  }),
);

// Bible sections that make up the "描述" block on a character page, in display order.
export const descriptionOrder = [
  '性格核心',
  '外形里的性格线索',
  '行为习惯',
  '表情与情绪',
  '喜欢 / 讨厌',
  '优点与课题',
  '道具的意义',
];

// Scene reference files → display names
export const scenes = [
  { file: 'Courtyard',     zh: '庭院',   en: 'Courtyard' },
  { file: 'Classroom',     zh: '教室',   en: 'Classroom' },
  { file: 'ArtClassRoom',  zh: '美术室', en: 'Art room' },
  { file: 'GamingRoom',    zh: '游戏室', en: 'Game room' },
  { file: 'ReadingRoom',   zh: '阅览室', en: 'Reading room' },
  { file: 'GreenHouse',    zh: '温室',   en: 'Greenhouse' },
  { file: 'NapRoom',       zh: '午睡室', en: 'Nap room' },
  { file: 'DiningRoom',    zh: '餐厅',   en: 'Dining room' },
  { file: 'Kitchen',       zh: '厨房',   en: 'Kitchen' },
  { file: 'EntryLobby',    zh: '门厅',   en: 'Entry lobby' },
  { file: 'Kindergarden-Map', zh: '平面图', en: 'Floor plan' },
];
