import { MotionProvider } from "@/components/providers/motion-provider";

export default function AuthLayout({ children }: LayoutProps<"/">) {
  return <MotionProvider>{children}</MotionProvider>;
}
