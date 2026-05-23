import React from "react";

type Props = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  loading?: boolean;
  loadingText?: string;
};

export default function LoadingButton({
  loading,
  loadingText,
  children,
  disabled,
  style,
  ...rest
}: Props) {
  return (
    <button
      {...rest}
      disabled={disabled || loading}
      style={{ minWidth: 110, ...style }}
    >
      {loading ? (
        <>
          <span className="spinner" aria-hidden /> {loadingText ?? "Working…"}
        </>
      ) : (
        children
      )}
    </button>
  );
}
