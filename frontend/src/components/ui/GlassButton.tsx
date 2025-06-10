import React from 'react';

interface GlassButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  children: React.ReactNode;
}

export default function GlassButton({ children, className = '', ...props }: GlassButtonProps) {
  return (
    <button
      className={`bg-white/20 backdrop-blur-md border border-white/30 text-white px-4 py-2 rounded-md shadow-lg transition-all hover:bg-white/30 active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}
