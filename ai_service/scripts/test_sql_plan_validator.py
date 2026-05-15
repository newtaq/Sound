from app.application.contracts import AISqlPlanItem
from app.application.sql import AISqlPlanValidator


def main() -> None:
    validator = AISqlPlanValidator()

    valid_plan = [
        AISqlPlanItem(
            sql="INSERT INTO ai_event_candidates (source_post_id, confidence) VALUES ('123', 0.9);",
            purpose="create event candidate",
            confidence=0.9,
        ),
        AISqlPlanItem(
            sql="SELECT id, title FROM events_search_view WHERE title ILIKE '%Кишлак%' LIMIT 10;",
            purpose="find related events",
            confidence=0.8,
        ),
    ]

    invalid_plan = [
        AISqlPlanItem(
            sql="UPDATE events SET title = 'bad' WHERE id = 1;",
            purpose="bad update",
        ),
        AISqlPlanItem(
            sql="SELECT * FROM events;",
            purpose="select without limit",
        ),
    ]

    print("VALID:", validator.validate_plan(valid_plan))
    print("INVALID:", validator.validate_plan(invalid_plan))


if __name__ == "__main__":
    main()
    
