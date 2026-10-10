/** Equipment desktop uses owner-supplied artwork; other images remain placeholders.
 * Approve campaign copy before launch. Recommended desktop: 1920 x 480 (4:1).
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
    desktopImage: "/promotions/equipment-desktop.png",
    mobileImage: "/promotions/equipment-mobile.png",
  },
  {
    id: "survey",
    label: "Free Lahore site survey",
    title: "Planning a CCTV setup in Lahore?",
    description: "A site survey is free. Installation is discussed and quoted after the survey.",
    actionLabel: "Learn about site surveys",
    to: "/#lahore-survey",
    desktopImage: "/promotions/survey-desktop.png",
    mobileImage: "/promotions/survey-mobile.png",
  },
] as const;
