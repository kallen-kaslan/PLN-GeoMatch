import { TablePagination, type TablePaginationProps } from "./TablePagination";

// Preserve the established accessible labels used by the main data tables.
export function PreviewPagination(props: TablePaginationProps) {
  return <TablePagination {...props} previousLabel={props.previousLabel ?? (props.context === "master" ? "Halaman sebelumnya" : undefined)} nextLabel={props.nextLabel ?? (props.context === "master" ? "Halaman berikutnya" : undefined)} />;
}
