import { MarketingSmoothScroll } from "@/components/motion/marketing-smooth-scroll";
import { ScrollProgress } from "@/components/motion/scroll-progress";

/** The public site follows the visitor's theme (light first) and owns the page-level motion. */
export default function MarketingLayout({ children }: LayoutProps<"/">) {
  return (
    <>
      <MarketingSmoothScroll />
      <ScrollProgress />
      {children}
    </>
  );
}
