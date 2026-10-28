import { useQuery } from '@tanstack/react-query';
import { api } from '../../api/client';
export function useDisplayUnits(){const {data}=useQuery({queryKey:['settings'],queryFn:api.getSettings});const fahrenheit=data?.temp_unit==='°F';const kilowatts=data?.energy_unit==='кВт·ч';return {temperature:(n:number|null|undefined)=>n==null?null:fahrenheit?n*1.8+32:n,tempUnit:fahrenheit?'°F':'°C',energy:(n:number)=>kilowatts?n*1000:n,energyUnit:kilowatts?'кВт·ч':'МВт·ч'};}
