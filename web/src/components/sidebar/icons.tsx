import type { ReactNode } from "react";

function Icon({ children, size = 18 }: { children: ReactNode; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {children}
    </svg>
  );
}

export const PanelIcon = () => (
  <Icon>
    <rect x="3" y="4" width="18" height="16" rx="3" />
    <path d="M9 4v16" />
  </Icon>
);
export const BackIcon = () => (
  <Icon>
    <path d="M15 6l-6 6 6 6" />
  </Icon>
);
export const ForwardIcon = () => (
  <Icon>
    <path d="M9 6l6 6-6 6" />
  </Icon>
);
export const ChatIcon = () => (
  <Icon>
    <path d="M4 5h16v11H9l-5 4z" />
  </Icon>
);
export const CodeIcon = () => (
  <Icon>
    <path d="M9 7l-5 5 5 5M15 7l5 5-5 5" />
  </Icon>
);
export const PlusIcon = () => (
  <Icon>
    <path d="M12 5v14M5 12h14" />
  </Icon>
);
export const SearchIcon = () => (
  <Icon>
    <circle cx="11" cy="11" r="6" />
    <path d="M20 20l-4.500-4.500" />
  </Icon>
);
export const FolderIcon = () => (
  <Icon>
    <path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
  </Icon>
);
export const ArtifactIcon = () => (
  <Icon>
    <path d="M12 3l8 4.500v9L12 21l-8-4.500v-9z" />
    <path d="M12 12l8-4.500M12 12v9M12 12L4 7.500" />
  </Icon>
);
export const CustomizeIcon = () => (
  <Icon>
    <path d="M4 7h10M18 7h2M4 17h2M10 17h10" />
    <circle cx="16" cy="7" r="2" />
    <circle cx="8" cy="17" r="2" />
  </Icon>
);
export const ChevronDownIcon = () => (
  <Icon size={14}>
    <path d="M6 9l6 6 6-6" />
  </Icon>
);
