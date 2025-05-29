# File: main.py
import os
import random 
import traceback 
from typing import List, Optional

from dotenv import load_dotenv 
from fastapi import FastAPI, HTTPException, Query 
from fastapi.middleware.cors import CORSMiddleware 
from pydantic import BaseModel 
from supabase import Client, create_client 
# from supabase.exceptions import APIError as PostgrestAPIError # Đã bỏ để dùng getattr

# --- Tải các biến môi trường ---
load_dotenv()

# --- Lấy URL và Key của Supabase ---
supabase_url: str = os.environ.get("SUPABASE_URL")
supabase_key: str = os.environ.get("SUPABASE_KEY")

if not supabase_url or not supabase_key:
    raise ValueError("Lỗi: SUPABASE_URL và SUPABASE_KEY cần được thiết lập trong file .env")

# --- Tạo Supabase client ---
supabase_client: Client = create_client(supabase_url, supabase_key)

# --- Khởi tạo FastAPI app ---
app = FastAPI(
    title="Real Estate Backend API (MVP 1 - Refactored)",
    description="API để tra cứu thông tin và giá bất động sản với bảng dim_projects.",
    version="1.2.0"
)

# --- Cấu hình CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"], 
    allow_headers=["*"], 
)

# --- Pydantic Models (Định nghĩa cấu trúc dữ liệu) ---

class PropertyDetailItem(BaseModel):
    description: Optional[str] = None
    project_name: Optional[str] = None 
    carpet_area: Optional[float] = None
    bedroom_count: Optional[int] = None
    toilet_count: Optional[int] = None
    property_view: Optional[str] = None
    door_direction: Optional[str] = None

class PropertyLookupResponse(BaseModel):
    estimated_unit_price: Optional[float] = None
    estimated_apartment_price: Optional[float] = None
    property_details: Optional[PropertyDetailItem] = None

class RegionItem(BaseModel):
    id: int
    name: str

class ProjectItem(BaseModel): 
    id: int 
    name: str 

class PropertyNumberItem(BaseModel):
    property_code: str  
    property_number: str 

class PropertyFeatures(BaseModel): 
    carpet_area: float
    bedroom_count: int
    toilet_count: int
    region_id: int

# --- API ENDPOINTS ---

@app.get("/")
async def read_root():
    return {"message": "Chào mừng bạn đến với Real Estate API! Backend đang hoạt động (với dim_projects)."}

@app.get("/lookup", response_model=PropertyLookupResponse)
async def lookup_property_price(
    region_name: str = Query(..., description="Tên Tỉnh/Thành phố, ví dụ: Hà Nội"),
    project_name_input: str = Query(..., alias="project_name", description="Tên dự án người dùng nhập"),
    property_number: Optional[str] = Query(None, description="Mã căn hộ (property_code) (Tùy chọn. Nếu bỏ trống, sẽ lấy căn đầu tiên của dự án)")
):
    try:
        property_data_item = None
        project_id_found = None

        # Bước 1: Tìm project_id từ project_name_input trong bảng dim_projects
        project_lookup_response = supabase_client.from_("dim_projects") \
            .select("id") \
            .eq("name", project_name_input) \
            .single() \
            .execute()
        
        error_obj_project = getattr(project_lookup_response, 'error', None)
        if error_obj_project:
            error_message = getattr(error_obj_project, 'message', str(error_obj_project))
            status_code = getattr(error_obj_project, 'status', 400) 
            if hasattr(error_obj_project, 'code') and "PGRST116" in error_obj_project.code:
                error_message = f"Không tìm thấy dự án với tên: '{project_name_input}'"
                status_code = 404
            raise HTTPException(status_code=status_code, detail=error_message)
        
        if project_lookup_response.data:
            project_id_found = project_lookup_response.data.get("id")
        
        if not project_id_found: 
             raise HTTPException(status_code=404, detail=f"Không tìm thấy ID cho dự án '{project_name_input}' (dữ liệu không hợp lệ).")

        base_query = supabase_client.from_("properties") \
            .select("id, property_code, property_number, carpet_area, bedroom_count, toilet_count, property_view, region_id, property_types(name), regions!inner(name), directions!properties_door_direction_id_fkey(name), dim_projects!inner(id, name)") \
            .eq("project_id", project_id_found) \
            .eq("regions.name", region_name)

        response_prop = None # Khởi tạo để tránh lỗi tham chiếu trước khi gán
        if property_number: 
            query = base_query.eq("property_code", property_number) 
            response_prop = query.single().execute()
            error_obj = getattr(response_prop, 'error', None) 
            if error_obj:
                error_message = getattr(error_obj, 'message', str(error_obj))
                status_code = getattr(error_obj, 'status', 400)
                if hasattr(error_obj, 'code') and "PGRST116" in error_obj.code:
                    error_message = f"Không tìm thấy căn hộ với mã '{property_number}' tại dự án '{project_name_input}' và tỉnh/thành '{region_name}'."
                    status_code = 404
                raise HTTPException(status_code=status_code, detail=error_message)
            property_data_item = response_prop.data
        else: 
            query = base_query.order("property_code").limit(1)
            response_prop = query.execute()
            error_obj = getattr(response_prop, 'error', None) 
            if error_obj:
                error_message = getattr(error_obj, 'message', str(error_obj))
                status_code = getattr(error_obj, 'status', 400)
                raise HTTPException(status_code=status_code, detail=error_message)
            if response_prop.data and len(response_prop.data) > 0:
                property_data_item = response_prop.data[0]

        if not property_data_item:
            raise HTTPException(status_code=404, detail=f"Không tìm thấy căn hộ nào tại dự án '{project_name_input}' và tỉnh/thành '{region_name}'.")

        property_data = property_data_item
        actual_project_name = property_data.get("dim_projects", {}).get("name") if property_data.get("dim_projects") else project_name_input
        door_direction_info = property_data.get("directions!properties_door_direction_id_fkey") or property_data.get("directions")
        door_direction_name = None
        if isinstance(door_direction_info, dict):
            door_direction_name = door_direction_info.get("name")
        elif isinstance(door_direction_info, list) and len(door_direction_info) > 0:
            door_direction_name = door_direction_info[0].get("name")
        
        display_prop_num = property_data.get("property_number") or property_data.get("property_code")

        property_details_for_response = PropertyDetailItem(
            description=f"Thông tin căn hộ {display_prop_num} tại dự án {actual_project_name}",
            project_name=actual_project_name,
            carpet_area=float(property_data.get("carpet_area", 0) or 0) if property_data.get("carpet_area") else None,
            bedroom_count=int(property_data.get("bedroom_count", 0) or 0) if property_data.get("bedroom_count") else None,
            toilet_count=int(property_data.get("toilet_count", 0) or 0) if property_data.get("toilet_count") else None,
            property_view=property_data.get("property_view", "Chưa có thông tin view"),
            door_direction=door_direction_name
        )

        estimated_unit_price = None
        estimated_apartment_price = None
        property_uuid = property_data.get("id") 

        if property_uuid:
            price_response = supabase_client.from_("price_history") \
                .select("price, price_per_m2, recorded_at") \
                .eq("property_id", property_uuid) \
                .order("recorded_at", desc=True) \
                .limit(1) \
                .maybe_single() \
                .execute()
            
            price_error_obj = getattr(price_response, 'error', None) 
            if price_error_obj:
                print(f"Lỗi API Supabase khi lấy lịch sử giá cho property_id {property_uuid}: {getattr(price_error_obj, 'message', str(price_error_obj))}")
            elif price_response.data:
                estimated_apartment_price = price_response.data.get("price")
                estimated_unit_price = price_response.data.get("price_per_m2")
        
        return PropertyLookupResponse(
            estimated_unit_price=estimated_unit_price,
            estimated_apartment_price=estimated_apartment_price,
            property_details=property_details_for_response
        )

    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Lỗi không xác định trong quá trình tra cứu: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Lỗi máy chủ nội bộ nghiêm trọng khi tra cứu: {str(e)}")

@app.get("/regions-list", response_model=List[RegionItem])
async def get_regions_list():
    try:
        response = supabase_client.from_("regions").select("id, name").order("name").execute()
        error_obj = getattr(response, 'error', None) 
        if error_obj:
            status_code = getattr(error_obj, 'status', 400)
            message = getattr(error_obj, 'message', str(error_obj))
            raise HTTPException(status_code=status_code, detail=message)
        return response.data
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Lỗi nghiêm trọng khi lấy danh sách vùng: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Lỗi máy chủ nội bộ khi xử lý yêu cầu: {str(e)}")

@app.get("/projects-list", response_model=List[ProjectItem])
async def get_projects_list(region_id: Optional[int] = Query(None, description="ID của Tỉnh/Thành để lọc dự án")):
    try:
        if region_id is not None:
            properties_response = supabase_client.from_("properties") \
                .select("project_id") \
                .eq("region_id", region_id) \
                .execute() 
            
            error_obj_props = getattr(properties_response, 'error', None)
            if error_obj_props:
                raise HTTPException(status_code=getattr(error_obj_props, 'status', 400), 
                                    detail=getattr(error_obj_props, 'message', str(error_obj_props)))

            if not properties_response.data:
                return [] 
            
            project_ids_with_duplicates = [p['project_id'] for p in properties_response.data if p.get('project_id') is not None]
            unique_project_ids = list(set(project_ids_with_duplicates))

            if not unique_project_ids: 
                return []

            response = supabase_client.from_("dim_projects") \
                .select("id, name") \
                .in_("id", unique_project_ids) \
                .order("name") \
                .execute()
        else:
            response = supabase_client.from_("dim_projects").select("id, name").order("name").execute()
        
        error_obj = getattr(response, 'error', None)
        if error_obj:
            status_code = getattr(error_obj, 'status', 400)
            message = getattr(error_obj, 'message', str(error_obj))
            raise HTTPException(status_code=status_code, detail=message)
        return response.data
        
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Lỗi khi lấy danh sách dự án: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/property-numbers-list", response_model=List[PropertyNumberItem])
async def get_property_numbers_list(
    project_id_input: int = Query(..., alias="project_id", description="ID của dự án để lọc mã căn hộ"),
    region_id: Optional[int] = Query(None, description="ID Tỉnh/Thành để lọc (tăng tính chính xác)") 
):
    try:
        # Đảm bảo bảng 'properties' có cột 'property_code' và 'property_number' (tên thân thiện)
        query = supabase_client.from_("properties") \
            .select("property_code, property_number") \
            .eq("project_id", project_id_input)
        
        if region_id is not None: 
            query = query.eq("region_id", region_id)
            
        response = query.order("property_number").execute() 
        error_obj = getattr(response, 'error', None) 
        if error_obj:
            status_code = getattr(error_obj, 'status', 400)
            message = getattr(error_obj, 'message', str(error_obj))
            if "column properties.property_number does not exist" in message:
                 print("LỖI CẤU TRÚC DATABASE: Cột 'property_number' không tồn tại trong bảng 'properties'.")
            raise HTTPException(status_code=status_code, detail=message)
        return response.data
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Lỗi khi lấy danh sách mã căn hộ: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/predict") 
async def predict_price(features: PropertyFeatures):
    print("Đã nhận các thông số để dự đoán:", features.dict())
    dummy_predicted_price = 1000000000 + (features.carpet_area * 50000000) + (features.bedroom_count * 200000000)
    dummy_predicted_price *= random.uniform(0.95, 1.05)
    return {"predicted_price_in_vnd": round(dummy_predicted_price)}

# --- CẬP NHẬT CHO DOCKER DEPLOYMENT ---
if __name__ == "__main__":
    import uvicorn
    # Khi deploy bằng Docker, Uvicorn cần lắng nghe trên host 0.0.0.0
    # Port có thể được lấy từ biến môi trường PORT do dịch vụ hosting cung cấp, mặc định là 8000
    # reload=False khi chạy trong production/Docker
    port_to_run = int(os.environ.get("PORT", 8000)) 
    uvicorn.run("main:app", host="0.0.0.0", port=port_to_run, reload=False)
