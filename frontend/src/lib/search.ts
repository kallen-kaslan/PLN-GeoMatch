export interface SearchIndexState { ready: boolean; processed_rows: number }
export interface SearchPage<T> { total: number; items: T[]; search_index?: SearchIndexState }

export const searchPreparing = (data?: { search_index?: SearchIndexState }) => data?.search_index?.ready === false;
export const searchRefreshInterval = (query: { state: { data: { search_index?: SearchIndexState } | undefined } }) => searchPreparing(query.state.data) ? 1000 : false;
