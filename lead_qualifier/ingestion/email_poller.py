from typing import List

def fetch_message_ids(service, query: str, max_results: int = 50) -> List[str]:
    """
    Fetch message IDs matching Gmail query.
    """
    user_id = "me"
    message_ids: List[str] = []

    req = service.users().messages().list(userId=user_id, q=query, maxResults=min(max_results, 500))
    while req is not None and len(message_ids) < max_results:
        resp = req.execute()
        msgs = resp.get("messages", [])
        for m in msgs:
            message_ids.append(m["id"])
            if len(message_ids) >= max_results:
                break
        req = service.users().messages().list_next(req, resp)

    return message_ids

def fetch_full_message(service, message_id: str) -> dict:
    user_id = "me"
    return service.users().messages().get(userId=user_id, id=message_id, format="full").execute()
