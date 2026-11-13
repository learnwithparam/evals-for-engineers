// States the text audit visits after the learner acts. Note-the-failures has its own port.
export type PageState = { name: string; path: string };

export const states: PageState[] = [
  { name: "trace review, note the failures", path: "http://127.0.0.1:8766/" },
];
