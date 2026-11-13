// The pages the text audit visits. The review app serves one step per port.
export type Route = { name: string; path: string };

export const routes: Route[] = [{ name: "trace review, mark the traces", path: "/" }];

// Button verbs the review app uses beyond the shared list, in lower case.
export const extraButtonVerbs: string[] = ["pass", "fail", "defer"];
