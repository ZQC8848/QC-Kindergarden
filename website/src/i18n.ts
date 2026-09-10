export type Lang = 'zh' | 'en';
export const langs: Lang[] = ['zh', 'en'];

const zh = {
  siteName: 'QC Kindergarten',
  tagline: '如有雷同\n纯属故意',
  intro: '以真实社交圈的性格为原型，AI 铸造的十二个角色和一部人设先行的情景喜剧。',
  nav: { characters: '角色', stories: '故事', places: '环境', research: '研究' },
  hero: { alt: '庭院大树下的全员合照，每个人都在干自己的事', hint: '点击照片里的人' },
  charactersTitle: '角色',
  charactersSub: '悬停看表情，点击进主页。',
  storiesTitle: '故事集',
  storiesSub: '发生过的记忆，与不影响连续性的番外。',
  storiesEmpty: '还没有故事。',
  filterAll: '全部',
  placesTitle: '幼儿园',
  placesSub: '每个地方都发生过一些事。点进去看是哪些。',
  placeStories: '在这里发生过的故事',
  placeNoStories: '这里还没有发生过故事。',
  otherPlaces: '其他地点',
  storyCount: { one: '个故事', many: '个故事' },
  readStory: '读这篇',
  cast: '出场',
  location: '地点',
  backHome: '回首页',
  allCharacters: '所有角色',
  phrase: '口头禅',
  profile: '设定',
  extras: '补充设定',
  memories: '记忆',
  memoriesSub: '同一件事，每个人记住的版本并不相同。',
  memoryEvents: '记忆事件',
  memoryEventsSub: '真实发生，并会影响之后的人物关系与行为。',
  extraTheater: '番外剧场',
  extraTheaterSub: '特别篇、假想与恶搞，不进入人物记忆。',
  extraNotice: '这是一篇番外，不进入任何角色的记忆。',
  appearsInExtras: '出演番外',
  perspectiveCount: '个记忆视角',
  knowledge: {
    witnessed: '亲历',
    heard: '听说',
    inferred: '推测',
    partial: '只知道一部分',
    secret: '知情但保密',
  },
  relations: '关系',
  turnaround: '三视图',
  threeD: '3D 模型准备中，先看三视图。',
  notTranslated: '英文版还没翻译，先显示中文。',
  footer: '一个人物先行的情景喜剧实验。',
  research: '研究说明',
  author: 'QC',
  prev: '上一个',
  next: '下一个',
  appearsIn: '出场的故事',
  noStories: '还没有出场的故事。',
  switchLang: 'English',
} as const;

/**
 * The English dictionary must carry exactly the Chinese one's keys; the values are free
 * text. Before, a missing key only surfaced in the audit script (tools/audit_en.py);
 * now `astro check` catches it.
 */
type Dict = {
  [K in keyof typeof zh]: (typeof zh)[K] extends string ? string : { [P in keyof (typeof zh)[K]]: string };
};

const en: Dict = {
  siteName: 'QC Kindergarten',
  tagline: 'Any resemblance\nis intentional',
  intro: 'Twelve AI-forged characters modelled on a real social circle, and a character-first sitcom.',
  nav: { characters: 'Characters', stories: 'Stories', places: 'Places', research: 'Research' },
  hero: {
    alt: 'Group photo under the courtyard tree, everyone doing their own thing',
    hint: 'Click a character in the photo',
  },
  charactersTitle: 'Characters',
  charactersSub: 'Hover for an expression, click for the profile.',
  storiesTitle: 'Stories',
  storiesSub: 'Shared memories and continuity-free side stories.',
  storiesEmpty: 'No stories yet.',
  filterAll: 'All',
  placesTitle: 'The kindergarten',
  placesSub: 'Something has happened in every one of these. Click a place to see what.',
  placeStories: 'Stories set here',
  placeNoStories: 'Nothing has happened here yet.',
  otherPlaces: 'Other places',
  storyCount: { one: 'story', many: 'stories' },
  readStory: 'Read',
  cast: 'Cast',
  location: 'Location',
  backHome: 'Home',
  allCharacters: 'All characters',
  phrase: 'Catchphrase',
  profile: 'Profile',
  extras: 'Additional notes',
  memories: 'Memories',
  memoriesSub: 'The same event leaves a different version with each character.',
  memoryEvents: 'Memory events',
  memoryEventsSub: 'Events that happened and can shape later relationships and behaviour.',
  extraTheater: 'Side stories',
  extraTheaterSub: 'Specials, imagined scenes and jokes outside character continuity.',
  extraNotice: 'This is a side story and does not enter any character memory.',
  appearsInExtras: 'Side-story appearances',
  perspectiveCount: 'memory perspectives',
  knowledge: {
    witnessed: 'Witnessed',
    heard: 'Heard',
    inferred: 'Inferred',
    partial: 'Partial knowledge',
    secret: 'Known but secret',
  },
  relations: 'Relationships',
  turnaround: 'Turnaround',
  threeD: '3D model coming; here is the turnaround for now.',
  notTranslated: 'Not translated yet. Showing the Chinese original.',
  footer: 'A character-first sitcom experiment.',
  research: 'Research notes',
  author: 'QC',
  prev: 'Previous',
  next: 'Next',
  appearsIn: 'Appears in',
  noStories: 'No stories yet.',
  switchLang: '中文',
};

const dict = { zh, en };

export function t(lang: Lang) {
  return dict[lang];
}

export function otherLang(lang: Lang): Lang {
  return lang === 'zh' ? 'en' : 'zh';
}
