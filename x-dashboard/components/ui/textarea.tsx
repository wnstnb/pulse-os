import * as React from "react";

import { cn } from "@/lib/utils";

export type TextareaProps = React.TextareaHTMLAttributes<HTMLTextAreaElement>;

export const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, ...props }, ref) => {
    return (
      <textarea
        ref={ref}
        className={cn(
          "min-h-[120px] w-full rounded-md border border-slate-700 bg-white px-3 py-2 text-sm text-slate-900",
          "focus:outline-none focus:ring-2 focus:ring-slate-400",
          className
        )}
        {...props}
      />
    );
  }
);

Textarea.displayName = "Textarea";
