/** Local placeholder artwork/copy; approve before launch. Recommended desktop: 1920 x 480 (4:1).
 * Mobile: 960 x 480 (2:1). Keep desktop image details on the right and retain live copy.
 */
export const promotionTiming = { slideMs: 8000, characterMs: 65, typingDelayMs: 300 } as const;

export const promotions = [
  {
    id: "equipment",
    label: "CCTV equipment",
    title: "Build around the equipment you need.",
    description: "Explore separate cameras, DVR/NVR recorders, surveillance storage, and accessories.",
    actionLabel: "Shop by category",
    to: "/#categories",
    desktopImage: "/promotions/equipment-desktop.svg",
    mobileImage: "/promotions/equipment-mobile.svg",
  },
  {
    id: "survey",
    label: "Free Lahore site survey",
    title: "Planning a CCTV setup in Lahore?",
    description: "A site survey is free. Installation is discussed and quoted after the survey.",
    actionLabel: "Learn about site surveys",
    to: "/#lahore-survey",
    desktopImage: "/promotions/survey-desktop.svg",
    mobileImage: "/promotions/survey-mobile.svg",
  },
] as const;
