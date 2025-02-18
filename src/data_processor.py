from .data_fetcher import fetch_data, fetch_multiple_data
import urllib.parse
from datetime import datetime
import re

def is_valid_date(date_str):
    if not isinstance(date_str, str):
        return False
    
    pattern = r'([A-Za-z]+ \d{4})'
    
    matches = re.findall(pattern, date_str)
    
    if len(matches) != 2:
        return False
    
    try:
        start_date = datetime.strptime(matches[0], '%b %Y')
        end_date = datetime.strptime(matches[1], '%b %Y')
        
        return True
    except ValueError:
        return False
    
def extract_experience_details(entry, experience_data, is_paged_list_component):
    entity = entry.get("components", {}).get("entityComponent", {})
    company_name = None
    job_title = None
    location = None
    company_logo_urn = None
    root_url = None
    image_path = None

    if entity:
        if entity.get('subtitle') and entity['subtitle'].get('text'):
            company_name = entity.get("subtitle", {}).get("text", "").split(" \u00b7 ")[0]
        if entity.get('titleV2') and entity['titleV2'].get('text'):
            job_title = entity.get("titleV2", {}).get("text", {}).get("text", "")
        if is_paged_list_component and entity.get("caption", {}) and "text" in entity.get("caption", {}):
            location = entity.get("caption", {}).get("text", "")
        elif entity.get('metadata') and entity['metadata'].get('text'):
            location = entity.get("metadata", {}).get("text", "").split(" \u00b7 ")[0]

        if entity.get("image"):
            company_logo_urn = entity.get("image", {}).get("attributes", [{}])[0].get("detailData", {}).get("*companyLogo")

        if company_logo_urn:
            for element in experience_data.get("included", []):
                if element.get("entityUrn") == company_logo_urn:
                    logo_resolution_result = element.get("logoResolutionResult")
                    if logo_resolution_result:
                        vector_image = logo_resolution_result.get("vectorImage", {})
                        if vector_image:
                            root_url = vector_image.get("rootUrl")
                            image_path = vector_image.get("artifacts", [{}])[-1].get("fileIdentifyingUrlPathSegment")
                            break

    return {
        "companyName": company_name,
        "jobTitle": job_title,
        "location": location,
        "companyLogo": f"{root_url}{image_path}" if root_url and image_path else None
    }
    
def get_correct_experience_data(record, pagedListComponent, experience_data):
    if pagedListComponent:
        for element in experience_data.get("included", []):
            if element.get("entityUrn") == pagedListComponent:
                record['companyName'] = record['jobTitle']
                if element.get("components", {}).get("elements", []) and len(element.get("components", {}).get("elements", [])) > 0:
                    record['jobTitle'] = element.get("components", {}).get("elements",[])[0].get("components", {}).get("entityComponent", {}).get("titleV2", {}).get("text", {}).get("text", "")
                
                for component in element.get("components", {}).get("elements", []):
                    if component.get("components", {}).get("entityComponent", {}).get("metadata", {}) and component.get("components", {}).get("entityComponent", {}).get("metadata", {}).get("text"):
                        record['location'] = component.get("components", {}).get("entityComponent", {}).get("metadata", {}).get("text", "")
                        break
    
    return record


def get_experience_datas(profile_urns, follower_number, cookies):
    profile_urls = [f'https://www.linkedin.com/voyager/api/graphql?variables=(profileUrn:{urllib.parse.quote(profile_urn)},sectionType:experience,locale:en_US)&queryId=voyagerIdentityDashProfileComponents.a62d9c6739ad5a19fdf61591073dec32' for profile_urn in profile_urns]

    experience_datas = fetch_multiple_data(profile_urls, follower_number, cookies)

    if experience_datas:
        records = []
    
        for url, experience_data in experience_datas.items():
            if experience_data and "included" in experience_data and experience_data["included"]:
                componentCount = sum(1 for item in experience_data["included"] if "components" in item and item["components"])
            if componentCount > 1 and experience_data and "included" in experience_data:
                for component in experience_data["included"]:
                    i = 0
                    flag = 0
                    for element in component.get("components", {}).get("elements", []):
                        entity_component = element.get("components", {}).get("entityComponent")
                        if entity_component:
                            if entity_component.get("subComponents", {}) is not None:
                                subcomponents = entity_component.get("subComponents", {}).get("components", [])
                                if isinstance(subcomponents, list) and len(subcomponents) > 0:
                                    components = subcomponents[0].get("components", {})
                                    if isinstance(components, dict) and "*pagedListComponent" in components:
                                        pagedListComponent = components.get("*pagedListComponent", "")
                                        flag = 1
                                        break
                        i += 1
                        
                    if flag == 1:
                        if i == 0:
                            record = extract_experience_details(component.get("components", {}).get("elements", [])[0], experience_data, 1)
                            record = get_correct_experience_data(record, pagedListComponent, experience_data)
                            record["profileUrl"] = url
                            records.append(record)
                        else:
                            record = extract_experience_details(component.get("components", {}).get("elements", [])[0], experience_data, 0)
                            record["profileUrl"] = url
                            records.append(record)
                        break

                    
            elif componentCount == 1 and len(experience_data["included"][0].get("components", {}).get("elements", [])): 
                record = extract_experience_details(experience_data["included"][0].get("components", {}).get("elements", [])[0], experience_data, 0)
                record["profileUrl"] = url
                records.append(record)

        return records
    else:
        print(f"Failed to retrieve experience data for the provided profile URNs")
        return {}
    