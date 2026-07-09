Shader "Carlos/Always In-Front" {
    Properties { 
        [MainColor] _BaseColor("Base Color", Color) = (1, 1, 1, 1)
        [MainTexture] _BaseMap("Base Map", 2D) = "white" { }
    }
    SubShader {
        Tags {
            "RenderType" = "Opaque"
            "Queue" = "Geometry+100"
            "RenderPipeline" = "UniversalPipeline"
        }

        Cull Back
        Blend SrcAlpha OneMinusSrcAlpha

        HLSLINCLUDE
        #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"

        struct VertexAttributes {
            float4 localPos : POSITION;
            float2 uv : TEXCOORD0;
        };

        //NOTE: Unity abbreviates Clip Space as HCS (Homogenous Clip Space), aka before the perspective divide into NDC (Normalized Device Coordinates).
        //Render Pipeline Space Transformations:
        //        M   *   V    *   P,   perspective divide      1/2x + 1/2
        //  Model → World → Camera → Clip (HCS)   →      NDC     → Viewport
        struct FragmentVaryings {
            float4 clipPos : SV_POSITION;
            float2 uv : TEXCOORD0;
        };

        TEXTURE2D(_BaseMap);
        SAMPLER(sampler_BaseMap);

        CBUFFER_START(UnityPerMaterial)
            float4 _BaseColor;
            float4 _BaseMap_ST;
        CBUFFER_END

        FragmentVaryings vert(VertexAttributes input) {
            FragmentVaryings output;
            output.clipPos = TransformObjectToHClip(input.localPos.xyz);
            output.uv = TRANSFORM_TEX(input.uv, _BaseMap);
            return output;
        }

        float4 frag(FragmentVaryings input) : SV_Target {
            float4 color = SAMPLE_TEXTURE2D(_BaseMap, sampler_BaseMap, input.uv);
            return _BaseColor * color;
        }
        ENDHLSL

        Pass {
            Name "Transparent Depth Pre-Pass"
            Tags { "LightMode" = "TransparentDepth" }
            ColorMask 0
            ZWrite On
            ZTest Always
        }

        Pass {
            Name "Ordinary Pass"
            Tags { "LightMode" = "TransparentPostPass" }
            ColorMask RGBA
            ZWrite On
            ZTest LEqual
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            ENDHLSL
        }
    }
}
