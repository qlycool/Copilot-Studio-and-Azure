"""
Azure Function entry point.
Timer-triggered function that runs the SharePoint → Azure AI Search indexer.

Deploy as an Azure Function App (Python v2 programming model).
The timer schedule is configurable via the INDEXER_SCHEDULE app setting
(defaults to every hour).
"""

import logging
import azure.functions as func

app = func.FunctionApp()

SCHEDULE = "%INDEXER_SCHEDULE%"  # App setting, default: "0 0 * * * *" (every hour)


@app.timer_trigger(
    schedule=SCHEDULE,
    arg_name="timer",
    run_on_startup=False,
)
def sharepoint_indexer(timer: func.TimerRequest) -> None:
    """Timer-triggered SharePoint indexer."""
    if timer.past_due:
        logging.warning("Timer is past due — running anyway")

    logging.info("SharePoint indexer triggered")

    try:
        from indexer import run_indexer
        stats = run_indexer()
        logging.info(stats.summary())
    except Exception as e:
        logging.error(f"Indexer run failed: {e}", exc_info=True)
        raise
