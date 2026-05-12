import { motion } from "framer-motion";
import { LayoutDashboard, Brain, Radio, History } from "lucide-react";
import { NavLink } from "react-router-dom";

const navItems = [
  { icon: LayoutDashboard, label: "Dashboard", path: "/dashboard" },
  { icon: Brain, label: "Strategy", path: "/strategy" },
  { icon: Radio, label: "Signals", path: "/signals" },
  { icon: History, label: "Activity", path: "/activity" },
];

export function DashboardSidebar() {
  return (
    <motion.aside
      initial={{ x: -20, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      transition={{ delay: 0.1 }}
      className="hidden lg:flex w-14 flex-col items-center gap-1.5 py-4 border-r border-border/30"
    >
      {navItems.map((item) => (
        <NavLink
          key={item.path}
          to={item.path}
          className={({ isActive }) =>
            `group relative flex h-9 w-9 items-center justify-center rounded-lg transition-all duration-200 ${
              isActive
                ? "bg-primary/20 text-primary shadow-[0_0_12px_hsl(38,96%,56%,0.25)]"
                : "text-muted-foreground hover:bg-muted/40 hover:text-foreground"
            }`
          }
        >
          {({ isActive }) => (
            <>
              {isActive && (
                <motion.div
                  layoutId="sidebar-active"
                  className="absolute inset-0 rounded-lg bg-primary/10 border border-primary/20"
                  transition={{ type: "spring", duration: 0.4 }}
                />
              )}
              <item.icon className="relative z-10 h-4 w-4" />
              <span className="absolute left-12 whitespace-nowrap rounded-md bg-popover/95 backdrop-blur-sm px-2 py-1 text-[10px] font-medium text-popover-foreground opacity-0 shadow-lg transition-opacity group-hover:opacity-100 pointer-events-none border border-border/50">
                {item.label}
              </span>
            </>
          )}
        </NavLink>
      ))}
    </motion.aside>
  );
}
