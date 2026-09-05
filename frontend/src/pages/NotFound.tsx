import { Link } from "react-router-dom";
import { Button, Card, EmptyState, PageContainer } from "../components/ui";

export function NotFound() {
  return (
    <PageContainer className="py-24">
      <Card solid edge className="mx-auto max-w-md p-8 text-center">
        <EmptyState
          title="404 — Page Not Found"
          description="The page or resource you requested could not be found."
          action={
            <Link to="/problems" className="mt-4 inline-block">
              <Button>← Return to problems</Button>
            </Link>
          }
        />
      </Card>
    </PageContainer>
  );
}
