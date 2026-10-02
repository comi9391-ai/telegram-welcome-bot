"""워프파이프 Meta 리드 광고 등록 스크립트.

영상 업로드 → 신청서(인스턴트 양식) 생성 → 광고 소재 → 광고(일시중지 상태)까지 한 번에 만든다.
광고는 항상 PAUSED로 만들어지므로, 광고관리자에서 확인 후 직접 켜야 비용이 나간다.

사용법:
    python meta_ads/launch_ad.py launch --video 영상.mp4 [--dry-run]
    python meta_ads/launch_ad.py leads --form-id <양식ID> [--out leads.csv]

필요한 환경변수는 meta_ads/.env.example 참고.
"""

import argparse
import csv
import json
import os
import sys
import time

import requests

API_VERSION = os.environ.get("META_API_VERSION", "v23.0")
GRAPH = f"https://graph.facebook.com/{API_VERSION}"

EXCHANGES = [
    ("binance", "바이낸스"),
    ("bybit", "바이비트"),
    ("okx", "OKX"),
    ("bitget", "비트겟"),
    ("upbit", "업비트"),
    ("bithumb", "빗썸"),
    ("other", "기타 / 아직 없음"),
]

LEAD_FORM = {
    "name": "워프파이프_자동매매_무료체험",
    "locale": "KO_KR",
    "questions": [
        {"type": "FULL_NAME", "key": "full_name"},
        {"type": "PHONE", "key": "phone_number"},
        {
            "type": "CUSTOM",
            "key": "exchange",
            "label": "사용 중인 거래소",
            "options": [{"key": k, "value": v} for k, v in EXCHANGES],
        },
    ],
    "context_card": {
        "title": "자동매매 프로그램 무료 체험 신청",
        "style": "PARAGRAPH_STYLE",
        "content": [
            "신청을 남겨주시면 담당자가 연락드려 설치와 세팅까지 도와드립니다.",
        ],
    },
    "thank_you_page": {
        "title": "신청이 접수됐습니다",
        "body": "영업일 기준 24시간 안에 남겨주신 연락처로 연락드리겠습니다.",
        "button_type": "VIEW_WEBSITE",
        "button_text": "워프파이프 둘러보기",
    },
}

AD_COPY = {
    "message": (
        "진입도, 손절도, 익절도 전부 자동으로.\n\n"
        "워프파이프는 AI 분석과 퀀트 전략으로 자동매매 시스템을 만드는 개발사입니다. "
        "전설적인 트레이더들의 매매법을 규칙으로 옮기고, 백테스트로 검증한 뒤 봇에 넣었습니다.\n\n"
        "지금 무료 체험을 신청하시면 설치와 세팅까지 직접 도와드립니다.\n\n"
        "※ 레버리지 거래는 원금 손실 위험이 있으며, 과거 성과가 미래 수익을 보장하지 않습니다."
    ),
    "title": "AI 퀀트 자동매매, 무료 체험 신청",
    "link_description": "개발사 워프파이프가 직접 세팅해드립니다",
}


def env(name, required=True, default=None):
    value = os.environ.get(name, default)
    if required and not value:
        sys.exit(f"환경변수 {name} 가 없습니다. meta_ads/.env.example 참고.")
    return value


def api(method, path, token, dry_run=False, files=None, **params):
    if dry_run:
        print(f"[dry-run] {method} {path}")
        print(json.dumps(params, ensure_ascii=False, indent=2))
        return {"id": f"DRYRUN_{path.strip('/').replace('/', '_')}"}
    data = {
        k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v
        for k, v in params.items()
    }
    data["access_token"] = token
    resp = requests.request(
        method,
        f"{GRAPH}/{path.lstrip('/')}",
        data=data if method != "GET" else None,
        params=data if method == "GET" else None,
        files=files,
        timeout=300,
    )
    body = resp.json()
    if "error" in body:
        err = body["error"]
        sys.exit(
            f"Meta API 오류 ({path}): {err.get('message')}\n"
            f"  상세: {err.get('error_user_msg', '-')}"
        )
    return body


def page_token(page_id, user_token, dry_run):
    if dry_run:
        return "DRYRUN_PAGE_TOKEN"
    return api("GET", page_id, user_token, fields="access_token")["access_token"]


def upload_video(ad_account, video_path, token, dry_run):
    print(f"영상 업로드 중: {video_path}")
    if dry_run:
        return api("POST", f"{ad_account}/advideos", token, True, name=os.path.basename(video_path))["id"]
    with open(video_path, "rb") as f:
        video_id = api(
            "POST",
            f"{ad_account}/advideos",
            token,
            files={"source": f},
            name=os.path.basename(video_path),
        )["id"]

    for _ in range(60):
        status = api("GET", video_id, token, fields="status")["status"]
        state = status.get("video_status")
        if state == "ready":
            break
        if state == "error":
            sys.exit(f"영상 처리 실패: {status}")
        time.sleep(5)
    else:
        sys.exit("영상 처리가 5분 넘게 끝나지 않았습니다. 광고관리자에서 상태를 확인하세요.")
    print(f"  영상 ID: {video_id}")
    return video_id


def video_thumbnail(video_id, token, dry_run):
    if dry_run:
        return "https://example.com/thumbnail.jpg"
    thumbs = api("GET", f"{video_id}/thumbnails", token)["data"]
    preferred = next((t for t in thumbs if t.get("is_preferred")), thumbs[0])
    return preferred["uri"]


def create_lead_form(page_id, ptoken, privacy_url, follow_up_url, dry_run):
    form = json.loads(json.dumps(LEAD_FORM))
    form["thank_you_page"]["website_url"] = follow_up_url
    form_id = api(
        "POST",
        f"{page_id}/leadgen_forms",
        ptoken,
        dry_run,
        privacy_policy={"url": privacy_url, "link_text": "개인정보처리방침"},
        follow_up_action_url=follow_up_url,
        **form,
    )["id"]
    print(f"  신청서 ID: {form_id}")
    return form_id


def launch(args):
    token = env("META_ACCESS_TOKEN", required=not args.dry_run)
    ad_account = env("META_AD_ACCOUNT_ID", required=not args.dry_run, default="act_DRYRUN")
    if not ad_account.startswith("act_"):
        ad_account = f"act_{ad_account}"
    page_id = env("META_PAGE_ID", required=not args.dry_run, default="DRYRUN_PAGE")
    adset_id = env("META_ADSET_ID", required=not args.dry_run, default="DRYRUN_ADSET")
    ig_user_id = env("META_INSTAGRAM_USER_ID", required=False)
    privacy_url = env("PRIVACY_POLICY_URL", required=not args.dry_run, default="https://example.com/privacy")
    follow_up_url = env("FOLLOW_UP_URL", required=not args.dry_run, default="https://example.com")

    if not os.path.isfile(args.video):
        sys.exit(f"영상 파일이 없습니다: {args.video}")

    video_id = upload_video(ad_account, args.video, token, args.dry_run)
    thumb = video_thumbnail(video_id, token, args.dry_run)

    print("신청서 생성 중")
    ptoken = page_token(page_id, token, args.dry_run)
    form_id = create_lead_form(page_id, ptoken, privacy_url, follow_up_url, args.dry_run)

    print("광고 소재 생성 중")
    story_spec = {
        "page_id": page_id,
        "video_data": {
            "video_id": video_id,
            "image_url": thumb,
            "message": AD_COPY["message"],
            "title": AD_COPY["title"],
            "link_description": AD_COPY["link_description"],
            "call_to_action": {
                "type": "SIGN_UP",
                "value": {"lead_gen_form_id": form_id},
            },
        },
    }
    if ig_user_id:
        story_spec["instagram_user_id"] = ig_user_id
    creative_id = api(
        "POST",
        f"{ad_account}/adcreatives",
        token,
        args.dry_run,
        name="워프파이프_자동매매_영상",
        object_story_spec=story_spec,
    )["id"]
    print(f"  소재 ID: {creative_id}")

    print("광고 생성 중 (일시중지 상태)")
    ad_id = api(
        "POST",
        f"{ad_account}/ads",
        token,
        args.dry_run,
        name="워프파이프_자동매매_영상_신청서",
        adset_id=adset_id,
        creative={"creative_id": creative_id},
        status="PAUSED",
    )["id"]

    print("\n완료. 광고는 일시중지 상태입니다. 광고관리자에서 미리보기 확인 후 켜세요.")
    print(f"  광고 ID: {ad_id}")
    print(f"  신청서 ID: {form_id}  (접수 내역 받기: launch_ad.py leads --form-id {form_id})")


def leads(args):
    token = env("META_ACCESS_TOKEN")
    page_id = env("META_PAGE_ID")
    ptoken = page_token(page_id, token, False)

    rows, after = [], None
    while True:
        params = {"fields": "created_time,field_data", "limit": 100}
        if after:
            params["after"] = after
        body = api("GET", f"{args.form_id}/leads", ptoken, **params)
        for lead in body.get("data", []):
            fields = {f["name"]: ", ".join(f.get("values", [])) for f in lead["field_data"]}
            rows.append(
                {
                    "접수시각": lead["created_time"],
                    "이름": fields.get("full_name", ""),
                    "연락처": fields.get("phone_number", ""),
                    "거래소": fields.get("exchange", ""),
                }
            )
        after = body.get("paging", {}).get("cursors", {}).get("after")
        if not body.get("paging", {}).get("next"):
            break

    with open(args.out, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["접수시각", "이름", "연락처", "거래소"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"{len(rows)}건 저장: {args.out}")


def main():
    parser = argparse.ArgumentParser(description="워프파이프 Meta 리드 광고 도구")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_launch = sub.add_parser("launch", help="영상 업로드 + 신청서 + 광고 생성")
    p_launch.add_argument("--video", required=True)
    p_launch.add_argument("--dry-run", action="store_true", help="API 호출 없이 보낼 내용만 출력")
    p_launch.set_defaults(func=launch)

    p_leads = sub.add_parser("leads", help="신청서 접수 내역을 CSV로 저장")
    p_leads.add_argument("--form-id", required=True)
    p_leads.add_argument("--out", default="leads.csv")
    p_leads.set_defaults(func=leads)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
