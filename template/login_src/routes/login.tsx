import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { Eye, EyeOff, Lock, User } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import smsImg from "@/assets/carousel-sms.jpg";
import botImg from "@/assets/carousel-bot.jpg";
import faxImg from "@/assets/carousel-fax.jpg";
import networkImg from "@/assets/carousel-network.jpg";
import pbxImg from "@/assets/carousel-pbx.jpg";
import reportsImg from "@/assets/carousel-reports.jpg";

export const Route = createFileRoute("/login")({
  head: () => ({
    meta: [
      { title: "Sign In ג€” Telecom Cloud Services" },
      { name: "description", content: "Sign in to manage SMS, BOT, Fax2Mail, Network, PBX and Reports." },
    ],
  }),
  component: LoginPage,
});

const slides = [
  { img: smsImg, title: "SMS Gateway", desc: "Send and receive SMS at scale with enterprise-grade reliability." },
  { img: botImg, title: "BOT Automation", desc: "Smart conversational bots to automate customer interactions." },
  { img: faxImg, title: "Fax2Mail", desc: "Modernize your fax workflow ג€” receive faxes directly to email." },
  { img: networkImg, title: "Network Solutions", desc: "End-to-end network infrastructure and managed services." },
  { img: pbxImg, title: "PBX Solutions", desc: "Cloud-based PBX for crystal-clear business communications." },
  { img: reportsImg, title: "Reports & Analytics", desc: "Real-time insights and reports across all your services." },
];

function LoginPage() {
  const [index, setIndex] = useState(0);
  const [showPassword, setShowPassword] = useState(false);

  useEffect(() => {
    const t = setInterval(() => setIndex((i) => (i + 1) % slides.length), 4000);
    return () => clearInterval(t);
  }, []);

  return (
    <main className="min-h-screen grid lg:grid-cols-2 bg-background">
      {/* Left: Carousel */}
      <section className="relative hidden lg:flex flex-col justify-between overflow-hidden bg-gradient-to-br from-[#0B2B4A] via-[#0E3B5C] to-[#0A1F38] p-12 text-white">
        <div className="relative z-10">
          <h1 className="text-2xl font-bold tracking-tight">NimbusTelecome</h1>
        </div>

        <div className="relative z-10 flex flex-col items-center justify-center flex-1">
          <div className="relative w-full max-w-md aspect-square">
            {slides.map((s, i) => (
              <img
                key={s.title}
                src={s.img}
                alt={s.title}
                width={1024}
                height={1024}
                loading={i === 0 ? "eager" : "lazy"}
                className={`absolute inset-0 w-full h-full object-contain transition-opacity duration-700 ease-in-out ${
                  i === index ? "opacity-100" : "opacity-0"
                }`}
              />
            ))}
          </div>

          <div className="mt-8 text-center max-w-md min-h-[96px]">
            <h2 className="text-3xl font-semibold mb-3 animate-fade-in" key={`t-${index}`}>
              {slides[index].title}
            </h2>
            <p className="text-white/70 leading-relaxed animate-fade-in" key={`d-${index}`}>
              {slides[index].desc}
            </p>
          </div>

          <div className="mt-8 flex gap-2">
            {slides.map((_, i) => (
              <button
                key={i}
                aria-label={`Go to slide ${i + 1}`}
                onClick={() => setIndex(i)}
                className={`h-1.5 rounded-full transition-all ${
                  i === index ? "w-8 bg-white" : "w-2 bg-white/30 hover:bg-white/50"
                }`}
              />
            ))}
          </div>
        </div>

        <p className="relative z-10 text-sm text-white/50">ֲ© 2026 NimbusTelecome Networks. All rights reserved.</p>

        {/* Decorative glows */}
        <div className="pointer-events-none absolute -top-32 -left-32 w-96 h-96 rounded-full bg-cyan-400/20 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-32 -right-32 w-96 h-96 rounded-full bg-blue-500/20 blur-3xl" />
      </section>

      {/* Right: Login form */}
      <section className="flex items-center justify-center p-6 sm:p-12">
        <div className="w-full max-w-md">
          <div className="mb-8 text-center">
            <div className="inline-flex h-14 w-14 items-center justify-center rounded-2xl bg-primary text-primary-foreground mb-4">
              <Lock className="h-7 w-7" />
            </div>
            <h2 className="text-2xl font-bold tracking-tight">Welcome back</h2>
            <p className="text-sm text-muted-foreground mt-1">Sign in to access your dashboard</p>
          </div>

          <form
            className="space-y-4"
            onSubmit={(e) => {
              e.preventDefault();
            }}
          >
            <div className="relative">
              <User className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input type="text" placeholder="Username" className="pl-10 h-11" required />
            </div>

            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                type={showPassword ? "text" : "password"}
                placeholder="Password"
                className="pl-10 pr-10 h-11"
                required
              />
              <button
                type="button"
                onClick={() => setShowPassword((v) => !v)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                aria-label="Toggle password visibility"
              >
                {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>

            <div className="flex justify-between text-sm">
              <a href="#" className="text-primary hover:underline">Forgot username?</a>
              <a href="#" className="text-primary hover:underline">Forgot password?</a>
            </div>

            <Button type="submit" className="w-full h-11 text-base">Sign In</Button>

            <p className="text-center text-sm text-muted-foreground">
              Don't have an account? <a href="#" className="text-primary hover:underline">Sign Up</a>
            </p>

            <div className="relative my-6">
              <div className="absolute inset-0 flex items-center"><span className="w-full border-t" /></div>
              <div className="relative flex justify-center text-xs uppercase">
                <span className="bg-background px-2 text-muted-foreground">Or</span>
              </div>
            </div>

            <Button type="button" variant="outline" className="w-full h-11">Sign in with SSO</Button>
          </form>
        </div>
      </section>
    </main>
  );
}
