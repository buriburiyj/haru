/** Row of the chat list page. `when` is already a relative date string ("방금", "3시간 전", "어제"). */
export type ChatListItem = {
  id: string;
  title: string;
  kind: "채팅" | "Code" | "Cowork";
  when: string;
  archived?: boolean;
};
