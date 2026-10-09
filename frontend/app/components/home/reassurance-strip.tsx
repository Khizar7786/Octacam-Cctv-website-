import { StoreIcon, type StoreIconName } from "~/components/ui/store-icon";
import "~/styles/reassurance.css";

const items: { title: string; detail: string; icon: StoreIconName }[] = [
  {
    title: "Cash on delivery",
    detail: "Cash on delivery only. Review your itemized total at checkout.",
    icon: "cash",
  },
  {
    title: "Product warranty",
    detail: "Warranty terms vary by product.",
    icon: "warranty",
  },
  {
    title: "Equipment delivery",
    detail: "Delivery fees and coverage are awaiting business approval.",
    icon: "delivery",
  },
  {
    title: "Support",
    detail: "Verified contact details and support policies are being prepared.",
    icon: "assistance",
  },
];

export function ReassuranceStrip() {
  return (
    <section aria-labelledby="reassurance-heading" className="reassurance-section" id="before-you-order">
      <h2 className="reassurance-heading" id="reassurance-heading">Before you order</h2>
      <ul className="reassurance-strip">
        {items.map((item) => (
          <li className="reassurance-item" key={item.title}>
            <span className="reassurance-icon" data-kind={item.icon}><StoreIcon inheritColor name={item.icon} /></span>
            <div className="reassurance-copy">
              <h3>{item.title}</h3>
              <p>{item.detail}</p>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
