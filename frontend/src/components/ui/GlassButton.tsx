import React from 'react';

interface GlassButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  children: React.ReactNode;
}

export default function GlassButton({ children, className = '', ...props }: GlassButtonProps) {
  return (
    <button
      className={`bg-white/60 backdrop-blur-sm border border-gray-300 text-gray-900 px-4 py-2 rounded-md shadow-lg transition-all hover:bg-white active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}
