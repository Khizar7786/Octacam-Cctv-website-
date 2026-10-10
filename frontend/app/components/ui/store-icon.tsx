import {
  FaBars,
  FaCalendarCheck,
  FaCartShopping,
  FaChevronDown,
  FaChevronLeft,
  FaChevronRight,
  FaEnvelope,
  FaHeadset,
  FaMagnifyingGlass,
  FaPhone,
  FaMinus,
  FaPlus,
  FaRotate,
  FaTrashCan,
  FaSliders,
  FaUser,
  FaWhatsapp,
  FaXmark,
} from "react-icons/fa6";
import { LuBanknote, LuHeadset, LuShield, LuTruck } from "react-icons/lu";
import { cn } from "~/lib/utils";

const icons = {
  search: { glyph: FaMagnifyingGlass, color: "text-primary", surface: "bg-accent" },
  menu: { glyph: FaBars, color: "text-primary", surface: "bg-accent" },
  close: { glyph: FaXmark, color: "text-primary", surface: "bg-accent" },
  cart: { glyph: FaCartShopping, color: "text-primary", surface: "bg-accent" },
  chevron: { glyph: FaChevronDown, color: "text-muted-foreground", surface: "bg-muted" },
  previous: { glyph: FaChevronLeft, color: "text-primary", surface: "bg-accent" },
  next: { glyph: FaChevronRight, color: "text-primary", surface: "bg-accent" },
  minus: { glyph: FaMinus, color: "text-primary", surface: "bg-accent" },
  plus: { glyph: FaPlus, color: "text-primary", surface: "bg-accent" },
  refresh: { glyph: FaRotate, color: "text-primary", surface: "bg-accent" },
  remove: { glyph: FaTrashCan, color: "text-error", surface: "bg-error-surface" },
  cash: { glyph: LuBanknote, color: "text-primary", surface: "bg-accent" },
  warranty: { glyph: LuShield, color: "text-primary", surface: "bg-accent" },
  delivery: { glyph: LuTruck, color: "text-primary", surface: "bg-accent" },
  assistance: { glyph: LuHeadset, color: "text-primary", surface: "bg-accent" },
  filters: { glyph: FaSliders, color: "text-primary", surface: "bg-accent" },
  account: { glyph: FaUser, color: "text-icon-account", surface: "bg-icon-account-surface" },
  survey: { glyph: FaCalendarCheck, color: "text-primary", surface: "bg-accent" },
  contact: { glyph: FaHeadset, color: "text-icon-phone", surface: "bg-icon-phone-surface" },
  phone: { glyph: FaPhone, color: "text-icon-phone", surface: "bg-icon-phone-surface" },
  email: { glyph: FaEnvelope, color: "text-icon-email", surface: "bg-icon-email-surface" },
  whatsapp: { glyph: FaWhatsapp, color: "text-icon-whatsapp", surface: "bg-icon-whatsapp-surface" },
} as const;

export type StoreIconName = keyof typeof icons;

/** Decorative icons accompany visible text or a control's accessible label. */
export function StoreIcon({ name, badge = false, inheritColor = false }: { name: StoreIconName; badge?: boolean; inheritColor?: boolean }) {
  const { glyph: Icon, color, surface } = icons[name];

  return (
    <span aria-hidden="true" className={cn("inline-flex shrink-0 items-center justify-center", !inheritColor && color, badge && `size-10 rounded-full ${surface}`)}>
      <Icon aria-hidden="true" className="size-5" focusable="false" />
    </span>
  );
}
