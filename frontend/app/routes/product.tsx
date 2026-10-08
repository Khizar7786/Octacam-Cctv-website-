import { data, useLoaderData, useRevalidator } from "react-router";
import { ProductDetailPage } from "~/components/catalog/product-detail-page";
import { buttonStyles } from "~/components/ui/button";
import { getPublicProductDetail } from "~/features/catalog/api";
import { ApiError } from "~/lib/api/client";
import { serverApiClient } from "~/lib/api/server-client.server";
import type { Route } from "./+types/product";

export function meta({ data: result }: Route.MetaArgs) {
  if (result?.state === "ready") {
    const product = result.product;
    return [
      { title: `${product.name} (${product.sku}) | OctaCam` },
      { name: "description", content: product.short_description || `View ${product.name}, model ${product.sku}, with current PKR price and availability.` },
    ];
  }
  return [{ title: "Product details | OctaCam" }];
}

export async function loader({ request, params }: Route.LoaderArgs) {
  if (!params.slug) throw data(null, { status: 404 });
  try {
    const product = await getPublicProductDetail(serverApiClient, params.slug, request.signal);
    return { state: "ready" as const, product };
  } catch (error) {
    if (request.signal.aborted) throw error;
    if (error instanceof ApiError && error.status === 404) throw data(null, { status: 404 });
    return { state: "error" as const };
  }
}

export default function Product() {
  const result = useLoaderData<typeof loader>();
  const revalidator = useRevalidator();
  if (result.state === "error") {
    return (
      <section aria-labelledby="product-error-title" className="max-w-[var(--reading-max)] rounded-lg border border-error bg-error-surface p-6" role="alert">
        <h1 className="text-[length:var(--font-size-heading)] font-bold" id="product-error-title">Product details could not be loaded</h1>
        <p className="mt-3">Please try again. We cannot confirm this product’s current price or stock right now.</p>
        <button className={buttonStyles({ variant: "outline", className: "mt-5" })} disabled={revalidator.state === "loading"} onClick={() => revalidator.revalidate()} type="button">Try again</button>
      </section>
    );
  }
  return <ProductDetailPage key={result.product.slug} product={result.product} />;
}
