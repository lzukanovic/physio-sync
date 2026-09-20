import { useParams } from "react-router-dom";

export default function Take() {
  const { id } = useParams();
  return <h2 className="text-xl font-semibold">Take {id}</h2>;
}
