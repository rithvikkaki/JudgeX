import { Link } from "react-router-dom";
import { Button, Card, EmptyState, PageContainer } from "../components/ui";

export function NotFound() {
  return (
    <PageContainer className="py-24">
      <Card className="mx-auto max-w-md p-8 text-center bg-graphite-surface border border-graphite-border rounded-lg">
        <EmptyState
          title="404 — ROUTE NOT FOUND"
          description="The requested URI resource does not map to any active JudgeX endpoint."
          action={
            <Link to="/problems" className="mt-4 inline-block">
              <Button className="btn-lime font-mono text-xs uppercase tracking-wider">
                ← Return to Problems
              </Button>
            </Link>
          }
        />
      </Card>
    </PageContainer>
  );
}
