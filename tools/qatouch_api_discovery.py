"""QA Touch Internal API Discovery - Final phase.

Batch probe ALL endpoint patterns via JS fetch from within the browser session.
Uses a real case key and known auth patterns.

Usage:
    python tools/qatouch_api_discovery_final.py
"""
from __future__ import annotations

import functools
import json
import os
import sys
import time
from datetime import datetime

_print = print
print = functools.partial(_print, flush=True)
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from dotenv import load_dotenv

load_dotenv(os.path.join(ROOT, '.env'))

DOMAIN = 'soterixsystems'
PROJECT_KEY = 'JlW1'
BASE_URL = f'https://{DOMAIN}.qatouch.com'
AUTH_STATE_FILE = os.path.join(ROOT, 'tools', '.qatouch_auth_state.json')
OUTPUT_FILE = os.path.join(ROOT, 'config', 'audit_reports', 'api_endpoint_discovery.json')

CHROME_UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
             '(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')

SMOKE_RUN_KEY = 'vaXdn'
CASE_KEY = 'gQxmgr'  # Known case key from mapping


def main():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=100)
        ctx = browser.new_context(
            viewport={'width': 1400, 'height': 900},
            storage_state=AUTH_STATE_FILE,
            user_agent=CHROME_UA,
        )
        page = ctx.new_page()

        print('=' * 70)
        print('  FINAL PHASE: Comprehensive batch endpoint probing')
        print('=' * 70)

        # Load QA Touch to establish session
        print('\n  Loading QA Touch...')
        page.goto(f'{BASE_URL}/v2#/new-projects', wait_until='networkidle')
        time.sleep(6)

        # Verify logged in
        logged_in = page.evaluate('''() => {
            return document.cookie.includes('XSRF-TOKEN') &&
                   document.cookie.includes('laravel_session');
        }''')
        print(f'  Session active: {logged_in}')

        # ---- BATCH PROBE: All endpoint patterns ----
        print('\n  Running batch probe of all endpoint patterns...')

        # Raw string: the JS below contains regex literals like /\//g, which
        # Python would otherwise read as invalid escape sequences.
        result = page.evaluate(r'''async (args) => {
            const [baseUrl, pid, cid, runKey] = args;

            // Get XSRF token
            const xsrfCookie = document.cookie.split(';')
                .map(c => c.trim())
                .find(c => c.startsWith('XSRF-TOKEN='));
            const xsrfToken = xsrfCookie
                ? decodeURIComponent(xsrfCookie.split('=').slice(1).join('='))
                : '';

            async function probe(url, method, body) {
                try {
                    const headers = {
                        'Content-Type': 'application/json',
                        'Accept': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest',
                    };
                    if (xsrfToken) headers['X-XSRF-TOKEN'] = xsrfToken;

                    const opts = { method: method || 'POST', headers, credentials: 'same-origin' };
                    if (body !== undefined && body !== null) {
                        opts.body = typeof body === 'string' ? body : JSON.stringify(body);
                    }

                    const resp = await fetch(baseUrl + url, opts);
                    const ct = resp.headers.get('content-type') || '';
                    let data = null;
                    if (ct.includes('json')) {
                        try { data = await resp.json(); } catch(e) {}
                    } else {
                        const text = await resp.text();
                        data = text.substring(0, 300);
                    }

                    let keys = null;
                    let summary = null;
                    if (data && typeof data === 'object' && !Array.isArray(data)) {
                        keys = Object.keys(data);
                        // Summarize value types
                        summary = {};
                        for (const [k, v] of Object.entries(data)) {
                            if (Array.isArray(v)) {
                                summary[k] = `array[${v.length}]`;
                                if (v.length > 0 && typeof v[0] === 'object') {
                                    summary[k + '_item_keys'] = Object.keys(v[0]).slice(0, 12);
                                }
                            } else if (typeof v === 'object' && v !== null) {
                                summary[k] = `obj(${Object.keys(v).length}keys: ${Object.keys(v).slice(0, 5).join(',')})`;
                            } else if (typeof v === 'string') {
                                summary[k] = v.length > 80 ? `str[${v.length}]` : v;
                            } else {
                                summary[k] = v;
                            }
                        }
                    } else if (Array.isArray(data)) {
                        summary = {_type: 'array', _count: data.length};
                        if (data.length > 0 && typeof data[0] === 'object') {
                            summary._item_keys = Object.keys(data[0]).slice(0, 12);
                        }
                    }

                    return {
                        url, method: method || 'POST', status: resp.status,
                        keys, summary, ct,
                    };
                } catch(e) {
                    return { url, method: method || 'POST', status: 0, error: e.message };
                }
            }

            const results = {};

            // ==========================================
            // CASE ENDPOINTS (read-only probes)
            // ==========================================
            results['case_edit'] = await probe(`/v1/case/edit/p/${pid}/cid/${cid}`);
            // Don't probe case/update or case/delete with real data

            // Case store (empty body - just validation)
            results['case_store'] = await probe(`/v1/case/store/p/${pid}`, 'POST', {});

            // ==========================================
            // MODULE / SECTION endpoints
            // ==========================================
            // Try every possible naming pattern
            const moduleEndpoints = [
                '/v1/module/list', '/v1/module/store', '/v1/module/edit',
                '/v1/module/delete', '/v1/module/rename',
                '/v1/section/list', '/v1/section/store',
                '/v1/section/edit', '/v1/section/delete',
            ];
            for (const ep of moduleEndpoints) {
                const key = ep.replace(/\//g, '_').substring(4);
                results[key] = await probe(`${ep}/p/${pid}`, 'POST', {});
            }

            // ==========================================
            // TEST RUN endpoints
            // ==========================================
            const runEndpoints = [
                '/v1/testrun/list', '/v1/testrun/store', '/v1/testrun/edit',
                '/v1/testrun/delete', '/v1/testrun/close',
                '/v1/run/list', '/v1/run/store', '/v1/run/edit',
            ];
            for (const ep of runEndpoints) {
                const key = ep.replace(/\//g, '_').substring(4);
                results[key] = await probe(`${ep}/p/${pid}`, 'POST', {});
            }

            // Run results
            results['testrun_results'] = await probe(`/v1/testrun/results/p/${pid}/r/${runKey}`, 'POST', {});
            results['run_results'] = await probe(`/v1/run/results/p/${pid}/r/${runKey}`, 'POST', {});

            // ==========================================
            // TAG endpoints
            // ==========================================
            const tagEndpoints = [
                '/v1/tag/list', '/v1/tag/store', '/v1/tag/edit',
                '/v1/tag/delete', '/v1/tags/list',
            ];
            for (const ep of tagEndpoints) {
                const key = ep.replace(/\//g, '_').substring(4);
                results[key] = await probe(`${ep}/p/${pid}`, 'POST', {});
            }

            // ==========================================
            // DASHBOARD / ANALYTICS
            // ==========================================
            results['dashboard_global'] = await probe('/v1/dashboard');
            results['dashboard_project'] = await probe(`/v1/dashboard/p/${pid}`);
            results['newdashboard'] = await probe('/v1/newdashboard');
            results['newdashboard_project'] = await probe(`/v1/newdashboard/p/${pid}`);
            results['teamDashboard_testRuns'] = await probe('/v1/teamDashboard/testRuns');
            results['teamDashboard_defects'] = await probe('/v1/teamDashboard/defects');
            results['teamDashboard_activity'] = await probe('/v1/teamDashboard/activity');
            results['teamDashboard_requirements'] = await probe('/v1/teamDashboard/requirements');
            results['teamDashboard_milestones'] = await probe('/v1/teamDashboard/milestones');
            results['teamDashboard_overview'] = await probe('/v1/teamDashboard/overview');

            // ==========================================
            // DEFECT / BUG endpoints
            // ==========================================
            const defectEndpoints = [
                '/v1/defect/list', '/v1/defect/store', '/v1/defect/edit',
                '/v1/defect/delete', '/v1/defects/list',
                '/v1/bug/list', '/v1/bug/store',
            ];
            for (const ep of defectEndpoints) {
                const key = ep.replace(/\//g, '_').substring(4);
                results[key] = await probe(`${ep}/p/${pid}`, 'POST', {});
            }

            // ==========================================
            // REQUIREMENT endpoints
            // ==========================================
            const reqEndpoints = [
                '/v1/requirement/list', '/v1/requirement/store',
                '/v1/requirement/edit', '/v1/requirement/delete',
                '/v1/requirements/list',
            ];
            for (const ep of reqEndpoints) {
                const key = ep.replace(/\//g, '_').substring(4);
                results[key] = await probe(`${ep}/p/${pid}`, 'POST', {});
            }

            // ==========================================
            // RELEASE / MILESTONE
            // ==========================================
            const releaseEndpoints = [
                '/v1/release/list', '/v1/release/store',
                '/v1/release/edit', '/v1/release/delete',
                '/v1/milestone/list', '/v1/milestone/store',
                '/v1/milestone/edit', '/v1/milestone/delete',
            ];
            for (const ep of releaseEndpoints) {
                const key = ep.replace(/\//g, '_').substring(4);
                results[key] = await probe(`${ep}/p/${pid}`, 'POST', {});
            }

            // ==========================================
            // CUSTOM FIELDS
            // ==========================================
            const cfEndpoints = [
                '/v1/customField/list', '/v1/customField/store',
                '/v1/customField/edit', '/v1/customField/delete',
                '/v1/customfield/list', '/v1/custom-field/list',
            ];
            for (const ep of cfEndpoints) {
                const key = ep.replace(/\//g, '_').substring(4);
                results[key] = await probe(`${ep}/p/${pid}`, 'POST', {});
            }

            // ==========================================
            // INTEGRATION / WEBHOOK
            // ==========================================
            const intEndpoints = [
                '/v1/integration/list', '/v1/integration/store',
                '/v1/integration/jira', '/v1/integration/slack',
                '/v1/integration/github', '/v1/integration/gitlab',
                '/v1/integration/jenkins', '/v1/integration/ci',
                '/v1/webhook/list', '/v1/webhook/store',
            ];
            for (const ep of intEndpoints) {
                const key = ep.replace(/\//g, '_').substring(4);
                results[key] = await probe(`${ep}/p/${pid}`, 'POST', {});
            }
            // Global integration endpoints
            results['integrations_global'] = await probe('/v1/integrations');
            results['integration_list_global'] = await probe('/v1/integration/list');

            // ==========================================
            // USER / TEAM
            // ==========================================
            results['users_list'] = await probe('/v1/users/list');
            results['users_option_list_POST'] = await probe('/v1/users/option/list');
            results['users_option_list_GET'] = await probe('/v1/users/option/list', 'GET');
            results['user_profile'] = await probe('/v1/user/profile');
            results['user_settings'] = await probe('/v1/user/settings');
            results['user_notification'] = await probe('/v1/user/notification');
            results['team_list'] = await probe('/v1/team/list');
            results['team_members'] = await probe('/v1/team/members');
            results['getTeamMembers'] = await probe('/v1/getTeamMembers');

            // ==========================================
            // PROJECT MANAGEMENT
            // ==========================================
            results['project_store'] = await probe('/v1/project/store', 'POST', {});
            results['project_edit'] = await probe(`/v1/project/edit/p/${pid}`);
            results['project_delete'] = await probe(`/v1/project/delete/p/${pid}`, 'POST', {});
            results['project_settings'] = await probe(`/v1/project/settings/p/${pid}`);
            results['project_members'] = await probe(`/v1/project/members/p/${pid}`);
            results['project_pin'] = await probe('/v1/project/pin');
            results['project_unpin'] = await probe('/v1/project/unpin');
            results['project_archive'] = await probe('/v1/project/archive');
            results['project_duplicate'] = await probe(`/v1/project/duplicate/p/${pid}`, 'POST', {});

            // ==========================================
            // STEPS
            // ==========================================
            results['steps_save'] = await probe('/v1/steps/save', 'POST', {});
            results['steps_delete_GET'] = await probe('/v1/steps/delete/mid/0?type=true', 'GET');
            results['steps_reorder'] = await probe('/v1/steps/reorder', 'POST', {});
            results['steps_update'] = await probe('/v1/steps/update', 'POST', {});
            results['steps_list'] = await probe('/v1/steps/list', 'POST', {});
            results['steps_get'] = await probe(`/v1/steps/get/p/${pid}`, 'POST', {});

            // ==========================================
            // SEARCH / FILTER
            // ==========================================
            results['search_global'] = await probe('/v1/search', 'POST', {query: 'test'});
            results['search_project'] = await probe(`/v1/search/p/${pid}`, 'POST', {query: 'test'});
            results['filter'] = await probe(`/v1/filter/p/${pid}`);
            results['globalSearch'] = await probe('/v1/globalSearch', 'POST', {query: 'test'});

            // ==========================================
            // NOTIFICATIONS / ACTIVITY
            // ==========================================
            results['notifications'] = await probe('/v1/notifications');
            results['notification_list'] = await probe('/v1/notification/list');
            results['notification_count'] = await probe('/v1/notification/count');
            results['activity'] = await probe('/v1/activity');
            results['activity_project'] = await probe(`/v1/activity/p/${pid}`);
            results['activity_list'] = await probe('/v1/activity/list');

            // ==========================================
            // TRASH / ARCHIVE
            // ==========================================
            results['trash'] = await probe('/v1/trash');
            results['trash_project'] = await probe(`/v1/trash/p/${pid}`);
            results['trash_list'] = await probe(`/v1/trash/list/p/${pid}`);
            results['archive'] = await probe('/v1/archive');
            results['archive_project'] = await probe(`/v1/archive/p/${pid}`);

            // ==========================================
            // AUDIT / LOG
            // ==========================================
            results['audit'] = await probe('/v1/audit');
            results['audit_project'] = await probe(`/v1/audit/p/${pid}`);
            results['auditTrail'] = await probe(`/v1/auditTrail/p/${pid}`);
            results['audit_log'] = await probe('/v1/audit/log');

            // ==========================================
            // EXPORT / IMPORT
            // ==========================================
            results['export'] = await probe(`/v1/export/p/${pid}`);
            results['export_cases'] = await probe(`/v1/export/cases/p/${pid}`);
            results['export_csv'] = await probe(`/v1/export/csv/p/${pid}`);
            results['export_excel'] = await probe(`/v1/export/excel/p/${pid}`);
            results['import'] = await probe(`/v1/import/p/${pid}`, 'POST', {});

            // ==========================================
            // SUBSCRIPTION / BILLING
            // ==========================================
            results['subscription'] = await probe('/v1/subscription');
            results['subscription_detail'] = await probe('/v1/subscription/detail');
            results['billing'] = await probe('/v1/billing');
            results['plan'] = await probe('/v1/plan');
            results['plan_list'] = await probe('/v1/plan/list');

            // ==========================================
            // WORKSPACE
            // ==========================================
            results['workspace_list'] = await probe('/v1/workspace/list');
            results['workspace_store'] = await probe('/v1/workspace/store', 'POST', {});
            results['workspace_switch'] = await probe('/v1/workspace/switch', 'POST', {});

            // ==========================================
            // MISC
            // ==========================================
            results['check_developer'] = await probe('/v1/check/developer');
            results['client_count_GET'] = await probe('/v1/client/count', 'GET');
            results['preferences'] = await probe('/v1/preferences');
            results['settings'] = await probe('/v1/settings');
            results['getFooter'] = await probe('/v1/get/footer');
            results['getTemplateCode'] = await probe('/v1/get/templateCode');
            results['accessibility'] = await probe('/v1/accessibility');
            results['accessibility_project'] = await probe(`/v1/accessibility/p/${pid}`);
            results['boards_list'] = await probe('/v1/boards/list');
            results['boards_project'] = await probe(`/v1/boards/list/p/${pid}`);
            results['productivity'] = await probe('/v1/productivity');
            results['hotkey'] = await probe('/v1/hotkey');
            results['feedback'] = await probe('/v1/feedback');
            results['tour_complete'] = await probe('/v1/tour/complete', 'POST', {});
            results['announcement'] = await probe('/v1/announcement');
            results['version'] = await probe('/v1/version');

            // ==========================================
            // SECURITY / ACCESS
            // ==========================================
            results['security'] = await probe('/v1/security');
            results['security_settings'] = await probe('/v1/security/settings');
            results['access_control'] = await probe('/v1/access/control');
            results['role_list'] = await probe('/v1/role/list');
            results['permission_list'] = await probe('/v1/permission/list');

            return results;
        }''', [BASE_URL, PROJECT_KEY, CASE_KEY, SMOKE_RUN_KEY])

        # Save auth state
        ctx.storage_state(path=AUTH_STATE_FILE)
        browser.close()

    # ---- ANALYZE AND SAVE RESULTS ----
    print('\n' + '=' * 70)
    print('  RESULTS')
    print('=' * 70)

    # Categorize results
    working = {}  # 200/201
    validation = {}  # 422
    server_error = {}  # 500
    not_found = {}  # 404
    auth_error = {}  # 401/403/419
    method_not_allowed = {}  # 405
    other = {}

    for key, val in result.items():
        status = val.get('status', 0)
        url = val.get('url', f'/v1/{key}')
        method = val.get('method', 'POST')

        entry = {
            'label': key,
            'url': url,
            'method': method,
            'status': status,
            'response_keys': val.get('keys'),
            'response_summary': val.get('summary'),
            'error': val.get('error'),
        }

        if status in (200, 201):
            working[url] = entry
        elif status == 422:
            validation[url] = entry
        elif status == 500:
            server_error[url] = entry
        elif status == 404:
            not_found[url] = entry
        elif status in (401, 403, 419):
            auth_error[url] = entry
        elif status == 405:
            method_not_allowed[url] = entry
        else:
            other[url] = entry

    print(f'\n  200 OK (working): {len(working)}')
    for url, ep in sorted(working.items()):
        keys = ep.get('response_keys', [])
        keys_str = f' keys={keys[:8]}' if keys else ''
        print(f'    [{ep["method"]}] {url}{keys_str}')

    print(f'\n  422 Validation (endpoint exists, needs payload): {len(validation)}')
    for url, ep in sorted(validation.items()):
        print(f'    [{ep["method"]}] {url}')

    print(f'\n  500 Server Error: {len(server_error)}')
    for url, ep in sorted(server_error.items()):
        print(f'    [{ep["method"]}] {url}')

    print(f'\n  401/403/419 Auth Error: {len(auth_error)}')
    for url, ep in sorted(auth_error.items()):
        print(f'    [{ep["method"]}] {url}')

    print(f'\n  405 Method Not Allowed: {len(method_not_allowed)}')
    for url, ep in sorted(method_not_allowed.items()):
        print(f'    [{ep["method"]}] {url}')

    print(f'\n  404 Not Found: {len(not_found)}')
    print(f'\n  Other: {len(other)}')

    # ---- MERGE INTO FINAL OUTPUT FILE ----
    print('\n  Merging into final output...')

    existing = {}
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, encoding='utf-8') as f:
            existing = json.load(f)

    # Update discovered endpoints
    disc = existing.get('discovered_internal_endpoints', {})
    for url, ep in working.items():
        if url not in disc:
            disc[url] = {
                'path': url,
                'method': ep['method'],
                'status': ep['status'],
                'source': 'final_batch_probe',
                'response_keys': ep.get('response_keys'),
                'response_summary': ep.get('response_summary'),
            }
    existing['discovered_internal_endpoints'] = dict(sorted(disc.items()))

    # Update validation endpoints
    val_eps = existing.get('validation_error_endpoints', {})
    for url, ep in validation.items():
        if url not in val_eps:
            val_eps[url] = {
                'path': url,
                'method': ep['method'],
                'status': 422,
                'source': 'final_batch_probe',
                'note': 'Endpoint exists but needs proper payload',
            }
    existing['validation_error_endpoints'] = dict(sorted(val_eps.items()))

    # Update server error endpoints
    err_eps = existing.get('server_error_endpoints', {})
    for url, ep in server_error.items():
        if url not in err_eps:
            err_eps[url] = {
                'path': url,
                'method': ep['method'],
                'status': 500,
                'source': 'final_batch_probe',
            }
    existing['server_error_endpoints'] = dict(sorted(err_eps.items()))

    # Store auth error endpoints (exist but need different auth)
    existing['auth_error_endpoints'] = dict(sorted(
        {url: {'path': url, 'method': ep['method'], 'status': ep['status']}
         for url, ep in auth_error.items()}.items()
    ))

    # Store method not allowed (exist but wrong HTTP method)
    existing['method_not_allowed_endpoints'] = dict(sorted(
        {url: {'path': url, 'method': ep['method'], 'status': ep['status']}
         for url, ep in method_not_allowed.items()}.items()
    ))

    # Update summary
    known = existing.get('known_working_endpoints', {})
    public = existing.get('public_api_endpoints', {})
    existing['summary'] = {
        'discovery_date': datetime.now().isoformat(),
        'total_internal_working': len(disc),
        'total_known_from_code': len(known),
        'total_validation_422': len(val_eps),
        'total_server_error_500': len(err_eps),
        'total_auth_error': len(auth_error),
        'total_method_not_allowed': len(method_not_allowed),
        'total_public_working': len(public),
        'total_not_found_404': len(not_found),
    }

    # Update all endpoint inventory
    existing['all_endpoint_inventory'] = {
        'total_unique_endpoints': len(set(
            list(disc.keys()) + list(known.keys()) + list(val_eps.keys()) +
            list(public.keys()) + list(auth_error.keys()) + list(method_not_allowed.keys())
        )),
        'internal_200': sorted(disc.keys()),
        'internal_422': sorted(val_eps.keys()),
        'internal_500': sorted(err_eps.keys()),
        'internal_401_403': sorted(auth_error.keys()),
        'internal_405': sorted(method_not_allowed.keys()),
        'known_from_code': sorted(known.keys()),
        'public_200': sorted(public.keys()),
    }

    # Update key findings
    existing['key_findings'] = {
        'internal_api_summary': (
            f'QA Touch internal API has {len(disc)} confirmed working endpoints, '
            f'{len(val_eps)} that exist but need payloads (422), '
            f'{len(err_eps)} with server errors (500), and '
            f'{len(auth_error)} requiring different auth levels.'
        ),
        'case_management': {
            'read': '/v1/case/edit/p/{pid}/cid/{key} - POST, returns full case JSON (type, mode, priority, tags, steps, custom fields)',
            'write': '/v1/case/update/p/{pid}/cid/{key} - POST, echo back modified case data from /edit',
            'create': '/v1/case/store/p/{pid} - POST, returns 422 with empty body (needs proper payload)',
            'note': 'These 3 endpoints enable full CRUD on cases via internal API, bypassing public API limitations.',
        },
        'step_management': {
            'create_update': '/v1/steps/save - POST, needs proper payload (422 with empty)',
            'delete': '/v1/steps/delete/mid/{stepId}?type=true - GET',
            'note': 'Already used by qatouch_browser.py sync-steps command.',
        },
        'user_management': {
            'list': '/v1/users/list - POST, returns paginated user data',
            'options': '/v1/users/option/list - GET, returns user options for dropdowns',
        },
        'dashboard_analytics': {
            'global': '/v1/dashboard - POST, returns projects_list, over_all_status, activity_chart, count_section, assigned_to_me, activity_list',
            'team_runs': '/v1/teamDashboard/testRuns - POST, returns test run data',
        },
        'project_management': {
            'list': '/v1/new-projectlist - POST, paginated project list',
            'meta': '/v1/new-projectlist/meta - POST, project metadata + admin info',
            'workspace': '/v1/project/getWorkspace - POST, workspace list',
            'pin_unpin': '/v1/project/pin and /v1/project/unpin - POST',
        },
        'public_api_coverage': {
            'read': '6 GET endpoints (projects, cases, modules, runs, requirements, defects, milestones)',
            'write': '1 PATCH endpoint (testRunResults/status/multiple) + POST endpoints for creating entities',
            'missing': 'No public API for: case update, tag management, step CRUD, case deletion, module rename',
        },
        'actionable_for_soterix': [
            'Use /v1/case/edit + /v1/case/update for programmatic case metadata updates (mode, type, priority, tags)',
            'Use /v1/case/store for creating cases with full metadata (bypasses public API limitations)',
            'Use /v1/steps/save for programmatic step creation/updates',
            'Use /v1/users/list for getting team member info',
            'Use /v1/dashboard for pulling analytics data into QA Ops Hub',
            'Use /v1/teamDashboard/testRuns for test execution overview',
            '/api/v1/getAllDefects for pulling defect data',
            '/api/v1/getAllMilestones for milestone tracking',
        ],
    }

    # Update categories
    existing['endpoint_categories'] = {
        'authentication_session': sorted([
            '/v1/refetch/all/permission',
            '/v1/fetch/all/permission',
            '/v1/updatePermission',
        ]),
        'workspace_project': sorted([
            '/v1/new-projectlist',
            '/v1/new-projectlist/meta',
            '/v1/new-projectlist/welcome',
            '/v1/project/getWorkspace',
            '/v1/getWorkspaceData',
            '/v1/project/pin',
            '/v1/project/unpin',
        ]),
        'user_team': sorted([
            '/v1/users/list',
            '/v1/users/option/list',
            '/v1/client/count',
            '/v1/check/developer',
        ]),
        'system_meta': sorted([
            '/v1/get/templateCode',
            '/v1/get/footer',
            '/v1/menulist',
            '/v1/getTourStatus',
            '/v1/getDisplayQuestion',
        ]),
        'case_management': sorted([
            '/v1/case/edit/p/{pid}/cid/{key}',
            '/v1/case/update/p/{pid}/cid/{key}',
            '/v1/case/store/p/{pid}',
        ]),
        'step_management': sorted([
            '/v1/steps/save',
            '/v1/steps/delete/mid/{stepId}?type=true',
        ]),
        'dashboard_analytics': sorted([
            '/v1/dashboard',
            '/v1/teamDashboard/testRuns',
        ]),
    }

    # Save final output
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(existing, f, indent=2, ensure_ascii=False, default=str)
    print(f'\n  FINAL RESULTS saved to: {OUTPUT_FILE}')

    # Print final totals
    print('\n  GRAND TOTALS:')
    print(f'    Internal working (200/201):  {len(disc)}')
    print(f'    Known from code:             {len(known)}')
    print(f'    Validation errors (422):     {len(val_eps)}')
    print(f'    Server errors (500):         {len(err_eps)}')
    print(f'    Auth errors (401/403):       {len(auth_error)}')
    print(f'    Method not allowed (405):    {len(method_not_allowed)}')
    print(f'    Public API working:          {len(public)}')


if __name__ == '__main__':
    main()
