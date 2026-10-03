import { isRouteErrorResponse } from "react-router";

export function getRouteErrorContent(error: unknown) {
  if (isRouteErrorResponse(error) && error.status === 404) {
    return {
      title: "Page not found",
      message: "The page you requested is unavailable. You can return to the home page.",
    };
  }

  // Thrown data is not automatically sanitized by React Router. Never display it.
  return {
    title: "Unable to load this page",
    message: "Please reload the page to try again, or return to the home page.",
  };
}
